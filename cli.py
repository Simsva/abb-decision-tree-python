#!/usr/bin/env python3

import sys
from typing import List
from collections.abc import Callable

class CLIError(Exception):
  pass

class Command:
  """Command class for use in CLI"""

  def __init__(self, function: Callable[[dict, List[str]], int], aliases: List[str], usage: str="", description: str=""):
    self.function = function
    self.aliases = aliases

    self.usage = usage
    self.description = description

  def add_alias(self, alias: str) -> None:
    self.aliases.append(alias)

# _Getch taken from https://stackoverflow.com/a/510364
class _Getch:
  def __init__(self):
    try:
      self.impl = _GetchWindows()
    except ImportError:
      self.impl = _GetchUnix()

    self.escape = {
      '\x1b': {
        '[': {
          'A': None,
          'B': None,
          'C': None,
          'D': None,
          'P': None,
        },
        '\x1b': '\x1b',
      },
    }

  def __call__(self):
    ch = self.impl()

    escape = self.escape
    # Iterate through tree of escape sequences, kind of like Xcompose
    while ch[-1] in escape:
      escape = escape[ch[-1]]
      if not isinstance(escape, dict):
        # Reached end of the dict
        if escape == None:
          return ch
        else:
          return escape
      else:
        ch += self.impl()

    if len(ch) > 1:
      # Return last character on failed escape sequence
      return ch[-1]
    else:
      # Return ch if not an escape sequence
      return ch

class _GetchUnix:
  def __init__(self):
    import tty, sys

  def __call__(self):
    import sys, tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
      tty.setraw(sys.stdin.fileno())
      ch = sys.stdin.read(1)
    finally:
      termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

class _GetchWindows:
  def __init__(self):
    import msvcrt

  def __call__(self):
    import msvcrt
    return msvcrt.getch()

default_stop_chars = [
  '\x03',
  '\x04',
  '\n',
  '\r',
]

default_invisible_chars = [
  "\x1b[A",
  "\x1b[B",
]

def default_cmd_quit(state, args):
  pass

def default_cmd_help(state, args):
  pass

def default_cmd_history(state, args):
  pass

class CLI:
  """Command-line interface"""

  def __init__(self, state: dict,
               prompt: str="> ",
               case_insensitive: bool=True,
               history_limit:int=1000,
               ):
    self.getch = _Getch()

    self._state = state
    self._prompt = prompt
    self._case_insensitive = case_insensitive
    self._history_limit = history_limit

    self._commands = []
    self._commandMaps = None
    self._quit_aliases = ["q", "quit"]
    self._help_aliases = ["h", "help"]

    self.messages = {
      "command_not_found": "No such command '{command}'\n",
      "command_error": "An error occured while running '{command}'\n",
      "command_invalid_status_code": "'{command}' returned a non-integer status code\n",
      "command_status_code": "'{command}' exited with status code '{status}'\n",
      "prompt_invalid": "Invalid prompt supplied\n",
      "aliases_invalid": "Invalid aliases supplied\n",
    }

  def set_quit_aliases(self, aliases: List[str]) -> None:
    if isinstance(aliases, list):
      self._quit_aliases = aliases
    else:
      raise CLIError(self.messages["aliases_invalid"])

  def set_help_aliases(self, aliases: List[str]) -> None:
    if isinstance(aliases, list):
      self._help_aliases = aliases
    else:
      raise CLIError(self.messages["aliases_invalid"])

  def register_command(self, command: Command) -> bool:
    if command in self._commands:
      return False
    else:
      self._commands.append(command)
      return True

  def _generate_command_maps(self) -> None:
    self._commandMaps = dict()
    for index, cmd in enumerate(self._commands):
      for alias in cmd.aliases:
        self._commandMaps[alias] = index

  def print_help(self) -> None:
    cmd_fmt = "{aliases} | {desc} | {name} {usage}"

    print(cmd_fmt.format(
      aliases='; '.join(self._help_aliases),
      desc="Print this help message",
      name=self._help_aliases[0],
      usage="",
    ))

    print(cmd_fmt.format(
      aliases='; '.join(self._quit_aliases),
      desc="Exit the program",
      name=self._quit_aliases[0],
      usage="",
    ))

    for cmd in self._commands:
      print(cmd_fmt.format(
        aliases='; '.join(cmd.aliases),
        desc=cmd.description,
        name=cmd.aliases[0],
        usage=cmd.usage,
      ))

  def _get_prompt(self) -> str:
    """Return the current command prompt"""

    try:
      if callable(self._prompt):
        return self._prompt(self._state)
      elif isinstance(self._prompt, str):
        return self._prompt.format(**self._state)
    except TypeError:
      # Supress TypeErrors (when __call__ does not take arguments)
      pass

    return None

  def _larrow(self, count:int) -> str:
    return "" if count == 0 else "\x1b[{}D".format(count)

  def input(self,
            prompt:str="",
            base_input:str="",
            stop_chars:List[str]=default_stop_chars,
            invisible_chars:List[str]=default_invisible_chars,
            ) -> str:
    """Input handler using self.getch"""

    import shutil

    out = base_input
    index = len(out)
    ch = ''
    while True:
      # Clear row and print prompt + input
      # TODO: Support input that spans over multiple rows
      w = shutil.get_terminal_size((80, 20)).columns
      sys.stdout.write('\r' + ' '*w
                       + '\r' + prompt + out + self._larrow(len(out)-index))
      sys.stdout.flush()
      ch = self.getch()

      if ch in stop_chars:
        break
      elif ch in invisible_chars:
        continue
      else:
        # Handle special characters
        if ch == "\x1b[C":
          # Right arrow
          if index < len(out): index += 1
        elif ch == "\x1b[D":
          # Left arrow
          if index > 0: index -= 1
        elif ch == '\x7f' or ch == '\b':
          # Backspace
          if index > 0:
            out = out[:index-1] + out[index:]
            index -= 1
        elif ch == "\x1b[P":
          # Delete
          if index < len(out):
            out = out[:index] + out[index+1:]
        else:
          # Print at index otherwise
          out = out[:index] + ch + out[index:]
          index += 1

    return out, ch

  def run(self) -> None:
    import shutil

    self._generate_command_maps()
    history = []
    current_cmd = ""

    while True:
      try:
        prompt = self._get_prompt()
        if not isinstance(prompt, str):
          raise CLIError(self.messages["prompt_invalid"])

        if len(history) >= self._history_limit:
          history.pop(0)
        i = len(history)
        last = i
        history.append("")

        while True:
          current_cmd, stop = self.input(
            prompt=prompt,
            stop_chars=default_stop_chars + ["\x1b[A", "\x1b[B"],
            # Use history at index i as base
            base_input=history[i],
          )

          # Navigate history with arrow keys
          w = shutil.get_terminal_size((80, 20)).columns
          if stop == '\x03':
            print()
            current_cmd = ""
            break
          elif stop == '\x04':
            if current_cmd == "":
              # Force quit command on ^D
              print(self._quit_aliases[0])
              current_cmd = self._quit_aliases[0]
              break
          elif stop == "\x1b[A":
            # Up arrow
            if i > 0:
              if i == last:
                # Save history
                history[last] = current_cmd
              i -= 1
              sys.stdout.write('\r' + ' '*w
                               + '\r')
              # sys.stdout.flush()
          elif stop == "\x1b[B":
            # Down arrow
            if i < last:
              i += 1
              sys.stdout.write('\r' + ' '*w
                               + '\r')
              # sys.stdout.flush()
          else:
            print()
            break

        history[len(history)-1] = current_cmd
        args = current_cmd.split()
        if len(args) == 0:
          history.pop()
          continue
        else:
          cmd_name = args[0].lower() if self._case_insensitive else args[0]

      except EOFError:
        print(self._quit_aliases[0])
        return
      except IndexError:
        # No command entered
        continue

      # TODO: Move built-in commands
      if cmd_name == "history":
        print('\n'.join([ f"{k+1:3d} {v}" for k,v in enumerate(history) ][-16:-1]))
      elif cmd_name in self._quit_aliases:
        return
      elif cmd_name in self._help_aliases:
        self.print_help()
      elif cmd_name in self._commandMaps:
        cmd = self._commands[self._commandMaps[cmd_name]]

        try:
          response = cmd.function(state=self._state, args=args)
        except (KeyboardInterrupt, EOFError):
          sys.stderr.write("Stopped execution of command\n")
          continue
        except Exception as e:
          sys.stderr.write(self.messages["command_error"].format(command=cmd_name))
          sys.stderr.write(str(e) + '\n')
          continue

        if not isinstance(response, int):
          sys.stderr.write(self.messages["command_invalid_status_code"].format(command=cmd_name))
        elif response != 0:
          sys.stderr.write(self.messages["command_status_code"].format(command=cmd_name, status=response))
      else:
        sys.stderr.write(self.messages["command_not_found"].format(command=cmd_name))

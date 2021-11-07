#!/usr/bin/env python3

import sys
from typing import List, TypeVar
from collections.abc import Callable

class Command:
  """Command class for use in CLI"""

  def __init__(self, function: Callable[[dict, List[str]], int], aliases: List[str], usage: str="", description: str=""):
    self.function = function
    self.aliases = aliases

    self.usage = usage
    self.description = description

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

def default_cmd_help(inter, state: dict, argv: list) -> int:
  def print_fmt(cmd):
    print(inter.help_format.format(
      aliases='; '.join(cmd.aliases),
      desc=cmd.description,
      name=cmd.aliases[0],
      usage=cmd.usage,
    ))

  if len(argv) < 2:
    for cmd in inter.commands:
      print_fmt(cmd)
  else:
    try:
      print_fmt(inter.get_command(argv[1]))
    except KeyError:
      sys.stderr.write(inter.messages["command_not_found"].format(command=argv[1]))
      return 1
  return 0

def default_cmd_quit(inter, state: dict, argv: list) -> int:
  return -1024

def default_cmd_history(inter, state: dict, argv: list) -> int:
  count = 15
  if len(argv) > 1:
    try:
      count = int(argv[1])
      if count < 1:
        sys.stderr.write(inter.messages["history_negative_count"])
        return 1
    except ValueError:
      sys.stderr.write(inter.messages["history_invalid_count"])
      return 1

  print('\n'.join([ f"{k+1:3d}  {v}" for k,v in enumerate(inter.history) ][-count-1:-1]))
  return 0

PromptType = TypeVar("PromptType", str, Callable)
class CLI:
  """Command-line interface"""

  def __init__(self, state: dict,
               prompt: PromptType="> ",
               case_insensitive: bool=True,
               history_limit:int=1000,
               ):
    self.getch = _Getch()

    self.state = state
    self.prompt = prompt
    self.case_insensitive = case_insensitive
    self.history_limit = history_limit

    self.commands = []
    self._command_maps = []
    self.help_format = "{aliases} | {desc} | {name} {usage}"

    # Registes built-in commands
    self.builtin_cmd_ids = {
      "help": self.register_command(Command(
        function=default_cmd_help,
        aliases=["h", "help"],
        usage="[command]",
        description="Print this help message",
      )),
      "quit": self.register_command(Command(
        function=default_cmd_quit,
        aliases=["q", "quit"],
        description="Quit the program",
      )),
      "history": self.register_command(Command(
        function=default_cmd_history,
        aliases=["history"],
        usage="[count=15]",
        description="Print the command history",
      )),
    }

    self.messages = {
      "command_not_found": "No such command '{command}'\n",
      "command_error": "An error occured while running '{command}'\n",
      "command_invalid_status_code": "'{command}' returned a non-integer status code\n",
      "command_status_code": "'{command}' exited with status code '{status}'\n",
      "command_already_registered": "Command was already registered\n",
      "command_overlapping_alias": "Another command is already using the alias '{alias}'\n",
      "prompt_invalid": "Invalid prompt supplied\n",
      "aliases_invalid": "Invalid aliases supplied\n",
      "id_out_of_range": "The specified ID is out of range",
      "history_negative_count": "Cannot print a zero or less history entries\n",
      "history_invalid_count": "Non-integer count of entries supplied\n",
    }

  def register_command(self, command: Command) -> int:
    """Add command to CLI and return its ID"""

    if command in self.commands:
      # TODO: Change exception types
      raise KeyError(self.messages["command_already_registered"])
    else:
      for alias in command.aliases:
        if alias in self._command_maps:
          raise KeyError(self.messages["command_overlapping_alias"].format(alias=alias))

      self.commands.append(command)
      return len(self.commands)-1

  def unregister_command(self, id: int) -> int:
    """Remove a command from CLI"""

    if id < len(self.commands):
      self.commands[id] = None
    else:
      raise IndexError(self.messages["id_out_of_range"])

  def _generate_command_maps(self) -> None:
    self._command_maps = dict()
    for index, cmd in enumerate(self.commands):
      if cmd != None:
        for alias in cmd.aliases:
          self._command_maps[alias] = index

  def get_command(self, alias: str) -> Command:
    if alias in self._command_maps:
      return self.commands[self._command_maps[alias]]
    else:
      raise KeyError(self.messages["command_not_found"].format(command=alias))

  def get_prompt(self) -> str:
    """Return the current command prompt"""

    try:
      if callable(self.prompt):
        return self.prompt(self.state)
      elif isinstance(self.prompt, str):
        return self.prompt.format(**self.state)
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
    import traceback

    self._generate_command_maps()
    self.history = []
    current_cmd = ""
    force_quit = False

    while True:
      prompt = self.get_prompt()
      if not isinstance(prompt, str):
        raise TypeError(self.messages["prompt_invalid"])

      if len(self.history) >= self.history_limit:
        self.history.pop(0)
      i = len(self.history)
      last = i
      self.history.append("")

      while True:
        current_cmd, stop = self.input(
          prompt=prompt,
          stop_chars=default_stop_chars + ["\x1b[A", "\x1b[B"],
          # Use history at index i as base
          base_input=self.history[i],
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
            # print(self._quit_aliases[0])
            # current_cmd = self._quit_aliases[0]
            force_quit = True
            break
        elif stop == "\x1b[A":
          # Up arrow
          if i > 0:
            if i == last:
              # Save history
              self.history[last] = current_cmd
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

      if force_quit:
        print()
        break

      self.history[len(self.history)-1] = current_cmd
      args = current_cmd.split()
      if len(args) == 0:
        self.history.pop()
        continue
      else:
        cmd_name = args[0].lower() if self.case_insensitive else args[0]

      if cmd_name in self._command_maps:
        cmd = self.commands[self._command_maps[cmd_name]]

        try:
          response = cmd.function(self, self.state, args)
        except (KeyboardInterrupt, EOFError):
          sys.stderr.write("Stopped execution of command\n")
          continue
        except Exception as e:
          sys.stderr.write(self.messages["command_error"].format(command=cmd_name))
          traceback.print_exc(file=sys.stderr)
          continue

        if not isinstance(response, int):
          sys.stderr.write(self.messages["command_invalid_status_code"].format(command=cmd_name))
        elif response == -1024:
          # Quit CLI
          print()
          break
        elif response != 0:
          sys.stderr.write(self.messages["command_status_code"].format(command=cmd_name, status=response))
      else:
        sys.stderr.write(self.messages["command_not_found"].format(command=cmd_name))

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

class CLI:
  """Command-line interface"""

  def __init__(self, state: dict, prompt: str="> ", case_insensitive: bool=True):
    self.__state = state
    self.__prompt = prompt
    self.__case_insensitive = case_insensitive

    self.__commands = []
    self.__commandMaps = None
    self.__quit_aliases = ["q", "quit"]
    self.__help_aliases = ["h", "help"]

    self.messages = {
      "command_not_found": "No such command '{command}'\n",
      "command_error": "An error occured while running '{command}'\n",
      "command_invalid_status_code": "'{command}' returned a non-integer status code\n",
      "command_status_code": "'{command}' exited with status code '{status}'\n",
      "prompt_invalid": "Invalid prompt supplied\n",
    }

  def set_quit_aliases(self, aliases: List[str]) -> None:
    if isinstance(aliases, list):
      self.__quit_aliases = aliases
    else:
      sys.stderr.write("Invalid aliases list\n")

  def set_help_aliases(self, aliases: List[str]) -> None:
    if isinstance(aliases, list):
      self.__help_aliases = aliases
    else:
      sys.stderr.write("Invalid aliases list\n")

  def register_command(self, command: Command) -> bool:
    if command in self.__commands:
      return False
    else:
      self.__commands.append(command)
      return True

  def __generate_command_maps(self) -> None:
    self.__commandMaps = dict()
    for index, cmd in enumerate(self.__commands):
      for alias in cmd.aliases:
        self.__commandMaps[alias] = index

  def print_help(self) -> None:
    cmd_fmt = "{aliases} | {desc} | {name} {usage}"

    print(cmd_fmt.format(
      aliases='; '.join(self.__help_aliases),
      desc="Print this help message",
      name=self.__help_aliases[0],
      usage="",
    ))

    print(cmd_fmt.format(
      aliases='; '.join(self.__quit_aliases),
      desc="Exit the program",
      name=self.__quit_aliases[0],
      usage="",
    ))

    for cmd in self.__commands:
      print(cmd_fmt.format(
        aliases='; '.join(cmd.aliases),
        desc=cmd.description,
        name=cmd.aliases[0],
        usage=cmd.usage,
      ))

  def __get_prompt(self) -> str:
    """Return the current command prompt"""

    try:
      if callable(self.__prompt):
        return self.__prompt(self.__state)
      elif isinstance(self.__prompt, str):
        return self.__prompt.format(**self.__state)
    except TypeError:
      # Supress TypeErrors (when __call__ does not take arguments)
      pass

    return None

  def run(self) -> None:
    self.__generate_command_maps()

    while True:
      try:
        prompt = self.__get_prompt()
        if not isinstance(prompt, str):
          raise CLIError(self.messages["prompt_invalid"])

        # TODO: History (curses?)
        args = input(prompt).split()
        cmd_name = args[0].lower() if self.__case_insensitive else args[0]
      except EOFError:
        print(self.__quit_aliases[0])
        return
      except IndexError:
        # No command entered
        continue

      if cmd_name in self.__quit_aliases:
        return
      elif cmd_name in self.__help_aliases:
        self.print_help()
      elif cmd_name in self.__commandMaps:
        cmd = self.__commands[self.__commandMaps[cmd_name]]

        try:
          response = cmd.function(state=self.__state, args=args)
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

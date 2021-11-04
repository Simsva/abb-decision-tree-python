#!/usr/bin/env python3

import cli

def dump(state, args):
  print(args)
  print(state)

  return 0

def inc(state, args):
  state["number"] += 1
  print(state["number"])

  return 0

def main():
  state = {
    "number": 1,
    "string": "hej"
  }
  interface = cli.CLI(state)

  cmd = cli.Command(
    function=inc,
    aliases=["inc", "add", "num"],
    description="Increment a number",
  )
  interface.register_command(cmd)

  cmd = cli.Command(
    function=dump,
    aliases=["dump"],
    usage="<args ...>",
    description="Dump state and arguments",
  )
  interface.register_command(cmd)

  interface.set_help_aliases(["?", "h", "help"])

  interface.run()

  print(state)

if __name__ == '__main__':
  main()

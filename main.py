#!/usr/bin/env python3

import os, sys
import json
import time

import cli
from decisiontree import *

def parse_data(filename, step=50):
  """Parse data in the format given by https://api.simsva.se/aidb/get_data/"""

  try:
    with open("data.json", 'r') as f:
      data_raw = json.loads(f.read())
      # TODO: Interpolate co2
      return [ {
        # Strip microseconds and return only hours
        "time_interval": time.strptime(x["time"][:19], "%Y-%m-%d %H:%M:%S").tm_hour,
        "volume": int(x["volume"]),
        "light": int(x["light"]),
        "temp": float(x["temp"]),
        "humidity": float(x["humidity"]),
      } for x in data_raw[::step] ]
  except json.JSONDecodeError:
    sys.stderr.write("Malformed JSON\n")
  except IOError:
    sys.stderr.write("Error while reading file\n")

def get_input(prompt, type_fn, default=None):
  """Handle user inputs of various data types"""

  if default == None:
    prompt = f"({type_fn.__name__}) {prompt} > "
  else:
    prompt = f"({type_fn.__name__}) ({default}) {prompt} > "

  while True:
    try:
      inp = input(prompt)
      if default != None and inp == "":
        return default
      else:
        return type_fn(inp)
    except ValueError:
      sys.stderr.write(f"Expected type '{type_fn}'\n")

def yes_no(prompt, default=False):
  """Ask user a yes or no question"""

  prompt = "({d}) {prompt}? ".format(prompt=prompt, d="Y/n" if default else "y/N")

  while True:
    inp = input(prompt).lower()
    if inp == "":
      return default
    elif inp == "n" or inp == "no":
      return False
    elif inp == "y" or inp == "yes":
      return True
    else:
      sys.stderr.write("Expected yes or no\n")

# CLI commands
def cmd_data_label(state, args):
  # Set label
  state["label"] = input("label > ")
  return 0

def cmd_data_load(state, args):
  # Load data from file
  filename = get_input("file", str, default="data.json")
  step = get_input("step", int, default=100)

  state["data"] = parse_data(filename, step=step)
  return 0

def cmd_data_print(state, args):
  # Print data
  print(state["data"])
  return 0

def cmd_tree_build(state, args):
  # Build tree
  try:
    if state["label"] in state["data"][0]:
      log = yes_no("log")
      state["tree"] = build_tree(state["data"], label, log=log)
    else:
      sys.stderr.write("Label not in data\n")
      return 1
  except IndexError:
    sys.stderr.write("No data\n")
    return 1
  return 0

def cmd_tree_print(state, args):
  # Print tree
  print_tree(state["tree"])
  return 0

def cmd_tree_save(state, args):
  # Save tree to file
  if state["tree"]:
    filename = get_input("file", str, default="tree.json")

    try:
      with open(filename, 'w') as f:
        f.write(json.dumps(state["tree"]))
        print("Done!")
    except IOError:
      sys.stderr.write("Error while writing file\n")
      return 1
  else:
    sys.stderr.write("No tree to save\n")
    return 1
  return 0

def cmd_tree_load(state, args):
  # Load tree from a file
  filename = get_input("file", str, default="tree.json")

  try:
    with open(filename, 'r') as f:
      state["tree"] = json.loads(f.read())
      print("Done!")
  except json.JSONDecodeError:
    sys.stderr.write("Malformed JSON\n")
    return 1
  except IOError:
    sys.stderr.write("Error while reading file\n")
    return 1
  return 0

def cmd_tree_guess(state, args):
  # Make a guess about a data point according to tree
  if state["tree"] and state["data"]:
    if state["label"] in state["data"][0]:
      data_point = dict()
      for k, v in state["data"][0].items():
        if k != state["label"]:
          data_point[k] = get_input(k, type(v), default=v)

      probs = guess_probability(guess(data_point, state["tree"]))
      print('\n'.join([ f"{k}: {v*100:.2f}%" for k,v in probs.items() ]))
    else:
      sys.stderr.write("Label not in data\n")
      return 1
  else:
    sys.stderr.write("No tree or data\n")
    return 1
  return 0

def main():
  header = "Decision tree generator"

  commands = [
    {
      "function": cmd_data_load,
      "aliases": ["dl", "data_load"],
      "description": "Load data from a file",
    },
    {
      "function": cmd_data_print,
      "aliases": ["dp", "data_print"],
      "description": "Print the data",
    },
    {
      "function": cmd_data_label,
      "aliases": ["dL", "data_label"],
      "description": "Set the label (field in data)",
    },
    {
      "function": cmd_tree_build,
      "aliases": ["tb", "tree_build"],
      "description": "Build tree from data",
    },
    {
      "function": cmd_tree_load,
      "aliases": ["tl", "tree_load"],
      "description": "Load tree from a file",
    },
    {
      "function": cmd_tree_save,
      "aliases": ["ts", "tree_save"],
      "description": "Save tree to a file",
    },
    {
      "function": cmd_tree_print,
      "aliases": ["tp", "tree_print"],
      "description": "Print tree",
    },
    {
      "function": cmd_tree_guess,
      "aliases": ["tg", "tree_guess"],
      "description": "Make a guess about a data point according to tree",
    },
    {
      "function": lambda state, args: 1 if print("{}\n{}".format(state, args)) else 0,
      "aliases": ["dump"],
      "description": "Dump state and args",
    },
  ]

  state = {
    "data": [],
    "label": '',
    "tree": None,
  }
  interface = cli.CLI(state)

  for cmd in commands:
    interface.register_command(cli.Command(**cmd))

  interface.set_help_aliases(["?", "h", "help"])
  interface.set_quit_aliases(["q", "quit", "exit"])

  print(header)
  interface.run()

if __name__ == '__main__':
  main()

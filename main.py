#!/usr/bin/env python3

import os, sys
import json
import time

import cli
from decisiontree import *

def parse_data(filename, offset=0, step=50):
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
      } for x in data_raw[offset::step] ]
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
      sys.stderr.write(f"Expected type '{type_fn.__name__}'\n")

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
def cmd_data_label(inter, state, argv):
  # Set label
  state["label"] = input("label > ")
  return 0

def cmd_data_load(inter, state, argv):
  # Load data from file
  filename = get_input("file", str, default="data.json")
  register = get_input("register", str, default='a')
  offset = get_input("offset", int, default=0)
  step = get_input("step", int, default=100)

  state["data"][register] = parse_data(filename, offset=offset, step=step)
  return 0

def cmd_data_print(inter, state, argv):
  # Print data
  r = get_input("register", str, default='a')

  if r in state["data"]:
    print(state["data"][r])
  else:
    sys.stderr.write("No data in register '{}'\n".format(r))
    return 1
  return 0

def cmd_tree_build(inter, state, argv):
  # Build tree
  dr = get_input("data register", str, default='a')
  tr = get_input("tree register", str, default='a')

  try:
    if state["label"] in state["data"][dr][0]:
      log = yes_no("log")
      state["tree"][tr] = build_tree(state["data"][dr], state["label"], log=log)
    else:
      sys.stderr.write("Label not in data\n")
      return 1
  except IndexError:
    sys.stderr.write("No data\n")
    return 1
  return 0

def cmd_tree_print(inter, state, argv):
  # Print tree
  r = get_input("register", str, default='a')

  if r in state["tree"]:
    print_tree(state["tree"][r])
  else:
    sys.stderr.write("No tree in register '{}'\n".format(r))
    return 1
  return 0

def cmd_tree_save(inter, state, argv):
  # Save tree to file
  r = get_input("register", str, default='a')

  if r in state["tree"]:
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

def cmd_tree_load(inter, state, argv):
  # Load tree from a file
  filename = get_input("file", str, default="tree.json")
  r = get_input("register", str, default='a')

  try:
    with open(filename, 'r') as f:
      state["tree"][r] = json.loads(f.read())
      print("Done!")
  except json.JSONDecodeError:
    sys.stderr.write("Malformed JSON\n")
    return 1
  except IOError:
    sys.stderr.write("Error while reading file\n")
    return 1
  return 0

def cmd_tree_guess(inter, state, argv):
  # Make a guess about a data point according to tree
  dr = get_input("data register", str, default='a')
  tr = get_input("tree register", str, default='a')

  if tr in state["tree"] and dr in state["data"]:
    if state["label"] in state["data"][dr][0]:
      data_point = dict()
      for k, v in state["data"][dr][0].items():
        if k != state["label"]:
          data_point[k] = get_input(k, type(v), default=v)

      probs = guess_probability(guess(data_point, state["tree"][tr]))
      print('\n'.join([ f"{k}: {v*100:.2f}%" for k,v in probs.items() ]))
    else:
      sys.stderr.write("Label not in data\n")
      return 1
  else:
    sys.stderr.write("No tree or data\n")
    return 1
  return 0

def cmd_tree_guess_register(inter, state, argv):
  # Guess with all points in data register
  dr = get_input("data register", str, default='a')
  tr = get_input("tree register", str, default='a')
  log = yes_no("print false points")

  if tr in state["tree"] and dr in state["data"]:
    if state["label"] in state["data"][dr][0]:
      f_points = []
      t, f = 0, 0
      for i, point in enumerate(state["data"][dr]):
        g = guess(point, state["tree"][tr])
        if verify_guess(state["label"], point, g):
          t += 1
        else:
          f += 1
          f_points.append((g, point))

      if log:
        print('\n'.join([ str(x[0]) + "-" + str(x[1]) for x in f_points ]))
      print("Total: {tot}  True: {t}  False: {f}\nAccuracy: {acc:.2f}%".format(tot=t+f, t=t, f=f, acc=t/(t+f)*100))
    else:
      sys.stderr.write("Label not in data\n")
      return 1
  else:
    sys.stderr.write("No tree or data\n")
    return 1
  return 0

# def cmd_forest_build(inter, state, argv):
#   # Build a random forest from data register
#   dr = get_input("data register", str, default='a')
#   fr = get_input("forest register", str, default='a')
#   c = get_input("count", int, default=2)
#   log = yes_no("log tree")

#   if dr in state["data"]:
#     if state["label"] in state["data"][dr][0]:
#       state["forest"][fr] = []
#       for i in range(c):
#         data = state["data"][dr][i::c]
#         state["forest"][fr].append(build_tree(
#           data,
#           state["label"],
#           log=log,
#         ))

#         print(f"Tree {i+1}/{c} done")
#     else:
#       sys.stderr.write("Label not in data\n")
#       return 1
#   else:
#     sys.stderr.write("No data in register\n")
#     return 1

#   return 0

# def cmd_forest_save(inter, state, argv):
#   # Save forest to file
#   r = get_input("register", str, default='a')

#   if r in state["forest"]:
#     filename = get_input("file", str, default="forest.json")

#     try:
#       with open(filename, 'w') as f:
#         f.write(json.dumps(state["forest"]))
#         print("Done!")
#     except IOError:
#       sys.stderr.write("Error while writing file\n")
#       return 1
#   else:
#     sys.stderr.write("No tree to save\n")
#     return 1
#   return 0

# def cmd_forest_load(inter, state, argv):
#   # Load forest from a file
#   filename = get_input("file", str, default="forest.json")
#   r = get_input("register", str, default='a')

#   try:
#     with open(filename, 'r') as f:
#       state["forest"][r] = json.loads(f.read())
#       print("Done!")
#   except json.JSONDecodeError:
#     sys.stderr.write("Malformed JSON\n")
#     return 1
#   except IOError:
#     sys.stderr.write("Error while reading file\n")
#     return 1
#   return 0

# def cmd_forest_guess(inter, state, argv):
#   # Make a guess about a data point according to tree
#   dr = get_input("data register", str, default='a')
#   fr = get_input("forest register", str, default='a')

#   if fr in state["forest"] and dr in state["data"]:
#     if state["label"] in state["data"][dr][0]:
#       data_point = dict()
#       for k, v in state["data"][dr][0].items():
#         if k != state["label"]:
#           data_point[k] = get_input(k, type(v), default=v)

#       probs = guess_probability(guess_forest(data_point, state["forest"][fr]))
#       print('\n'.join([ f"{k}: {v*100:.2f}%" for k,v in probs.items() ]))
#     else:
#       sys.stderr.write("Label not in data\n")
#       return 1
#   else:
#     sys.stderr.write("No tree or data\n")
#     return 1
#   return 0

# def cmd_forest_guess_register(inter, state, argv):
#   # Guess with all points in data register
#   dr = get_input("data register", str, default='a')
#   fr = get_input("forest register", str, default='a')
#   log = yes_no("print false points")

#   if fr in state["forest"] and dr in state["data"]:
#     if state["label"] in state["data"][dr][0]:
#       f_points = []
#       t, f = 0, 0
#       for i, point in enumerate(state["data"][dr]):
#         g = guess_forest(point, state["forest"][fr])
#         if verify_guess(state["label"], point, g):
#           t += 1
#         else:
#           f += 1
#           f_points.append((g, point))

#       if log:
#         print('\n'.join([ str(x[0]) + "-" + str(x[1]) for x in f_points ]))
#       print("Total: {tot}  True: {t}  False: {f}\nAccuracy: {acc:.2f}%".format(tot=t+f, t=t, f=f, acc=t/(t+f)*100))
#     else:
#       sys.stderr.write("Label not in data\n")
#       return 1
#   else:
#     sys.stderr.write("No tree or data\n")
#     return 1
#   return 0

def cmd_register_list(inter, state, argv):
  # Print all registers of specified type
  def print_keys(d):
    print(', '.join(d.keys()))

  if len(argv) > 1:
    if argv[1] == 't' or argv[1] == "tree":
      print_keys(state["tree"])
    elif argv[1] == 'd' or argv[1] == "data":
      print_keys(state["data"])
    else:
      sys.stderr.write("Invalid register type\n")
      return 1
  else:
    sys.stderr.write("No register type supplied\n")
    return 1
  return 0

def get_prompt(state):
  """Returns a prompt based on state"""

  if state["label"] != "":
    return f"({state['label']}) > "
  else:
    return "> "

def main():
  header = "Decision tree generator"

  commands = [
    {
      "function": cmd_data_load,
      "aliases": ["dl", "data_load"],
      "description": "Load data from a file",
      "category": "Data",
    },
    {
      "function": cmd_data_print,
      "aliases": ["dp", "data_print"],
      "description": "Print the data",
      "category": "Data",
    },
    {
      "function": cmd_data_label,
      "aliases": ["dL", "data_label"],
      "description": "Set the label (field in data)",
      "category": "Data",
    },
    {
      "function": cmd_tree_build,
      "aliases": ["tb", "tree_build"],
      "description": "Build tree from data",
      "category": "Tree",
    },
    {
      "function": cmd_tree_load,
      "aliases": ["tl", "tree_load"],
      "description": "Load tree from a file",
      "category": "Tree",
    },
    {
      "function": cmd_tree_save,
      "aliases": ["ts", "tree_save"],
      "description": "Save tree to a file",
      "category": "Tree",
    },
    {
      "function": cmd_tree_print,
      "aliases": ["tp", "tree_print"],
      "description": "Print tree",
      "category": "Tree",
    },
    {
      "function": cmd_tree_guess,
      "aliases": ["tg", "tree_guess"],
      "description": "Make a guess about a data point according to tree",
      "category": "Tree",
    },
    {
      "function": cmd_tree_guess_register,
      "aliases": ["tgr", "tree_guess_register"],
      "description": "Make a guess about all data points in a register according to tree",
      "category": "Tree",
    },
    # {
    #   "function": cmd_forest_build,
    #   "aliases": ["fb", "forest_build"],
    #   "description": "Build forest from data",
    #   "category": "Forest",
    # },
    # {
    #   "function": cmd_forest_load,
    #   "aliases": ["fl", "forest_load"],
    #   "description": "Load forest from a file",
    #   "category": "Forest",
    # },
    # {
    #   "function": cmd_forest_save,
    #   "aliases": ["fs", "forest_save"],
    #   "description": "Save forest to a file",
    #   "category": "Forest",
    # },
    # {
    #   "function": cmd_forest_guess,
    #   "aliases": ["fg", "forest_guess"],
    #   "description": "Make a guess about a data point according to forest",
    #   "category": "Forest",
    # },
    # {
    #   "function": cmd_forest_guess_register,
    #   "aliases": ["fgr", "forest_guess_register"],
    #   "description": "Make a guess about all data points in a register according to forest",
    #   "category": "Forest",
    # },
    {
      "function": cmd_register_list,
      "aliases": ["rl", "register_list"],
      "description": "List all registers of register type",
      "category": "Register",
    },
    {
      "function": lambda inter, state, args: 1 if print("{}\n{}".format(state, args)) else 0,
      "aliases": ["dump"],
      "description": "Dump state and args",
      "category": "Debug",
    },
  ]

  state = {
    "label": '',
    "data": dict(),
    "tree": dict(),
    # "forest": dict(),
  }
  inter= cli.CLI(
    state=state,
    prompt=get_prompt,
    case_insensitive=False,
  )

  for cmd in commands:
    inter.register_command(cli.Command(**cmd))

  print(header)
  inter.run()

if __name__ == '__main__':
  main()

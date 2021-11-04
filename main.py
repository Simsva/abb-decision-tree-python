#!/usr/bin/env python3

import os, sys
import json
import time

def question(field, val):
  return {"field": field, "val": val}

def ask(q, data_point):
  val = data_point[q["field"]]

  if isinstance(val, int) or isinstance(val, float):
    return val >= q["val"]
  else:
    return val == q["val"]

def partition(q, data):
  t, f = [], []
  for point in data:
    if ask(q, point):
      t.append(point)
    else:
      f.append(point)

  return t, f

def count_label(data, label_field):
  count = dict()
  for x in data:
    if x[label_field] not in count:
      count[x[label_field]] = 0
    count[x[label_field]] += 1

  return count

def gini(data, label_field):
  """Calculate chance of guessing the wrong label"""

  data_len = len(data)

  label_count = count_label(data, label_field)

  impurity = 1
  for label in label_count:
    probability = label_count[label] / data_len
    impurity -= probability**2

  return impurity

def info_gain(t, f, uncertainty, label_field):
  """Calculate loss of uncertainty (gain of information) after partitioning"""

  p = len(t) / (len(t) + len(f))
  return uncertainty - p*gini(t, label_field) - (1-p)*gini(f, label_field)

def calculate_best_partition(data, label_field, log=False, log_spacing=50, log_pad=''):
  """Find best question to ask"""

  best_gain = 0
  best_q = None
  uncertainty = gini(data, label_field)

  # All possible fields
  fields = [ x for x in data[0] if x != label_field ]

  # Calculate amount of iterations
  unique = dict([ (field, set([ x[field] for x in data ])) for field in fields ])
  count = sum([ len(x) for x in unique.values() ])
  i = 0

  for field in fields:
    for val in unique[field]:
      if log and ((i := i+1) % 50 == 1 or i == count):
        print(log_pad+"Question: {}/{}".format(i, count))
      q = question(field, val)
      t, f = partition(q, data)

      # Basic optimization, do not continue if the data is not partitioned
      if len(t) == 0 or len(f) == 0: continue

      gain = info_gain(t, f, uncertainty, label_field)
      if gain > best_gain:
        best_gain = gain
        best_q = q

  return best_gain, best_q

def build_tree(data, label_field, log=False, level=0):
  pad = "{pad}{level} ".format(pad=' '*level, level=level)

  gain, q = calculate_best_partition(data, label_field, log=log, log_pad=pad)
  if log: print(pad+"Question done")

  if gain == 0:
    if log: print(pad+"End node")
    # return data
    return count_label(data, label_field)

  t, f = partition(q, data)
  t_branch = build_tree(t, label_field, log=log, level=level+1)
  f_branch = build_tree(f, label_field, log=log, level=level+1)

  if log: print(pad+"Branch done")
  return {"q": q, "t": t_branch, "f": f_branch}

def print_tree(node, level=0):
  pad = "{pad}{level} ".format(pad="  "*level, level=level)

  if 'q' in node:
    print(pad+"{field} >= {val}".format(**node['q']))

    print(pad+"--> True:")
    print_tree(node['t'], level=level+1)

    print(pad+"--> False:")
    print_tree(node['f'], level=level+1)
  else:
    print(pad+"Predict", str(node))

def guess(data_point, node):
  if 'q' in node:
    if ask(node['q'], data_point):
      return guess(data_point, node['t'])
    else:
      return guess(data_point, node['f'])
  else:
    return node

def guess_probability(guess):
  total = sum(guess.values())
  probs = dict()
  for label in guess.keys():
    probs[label] = guess[label] / total
  return probs

def parse_data(filename, step=50):
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

def cli():
  header = """\
Decision tree generator"""

  oper_help = """\
Common:
  q  | Quit
  h  | Print this help message

Data:
  dl | Load data from file
  dp | Print data
  dL | Set label (field in data)

Tree:
  tb | Build tree from data
  tl | Load tree from file
  ts | Save tree to file
  tp | Print tree"""

  data = []
  label = ""
  tree = None

  print(header)
  while True:
    oper = input("> ")

    if oper == "":
      continue
    if oper == "q":
      os.exit()

    elif oper == "h":
      # Help
      print(oper_help)

    # Data operations
    elif oper == "dL":
      # Set label
      if data:
        while True:
          label = input("label > ")
          if not label in data[0]:
            sys.stderr.write("Label not in data\n")
          else:
            break
      else:
        label = input("label > ")
    elif oper == "dl":
      # Load
      filename = get_input("file", str, default="data.json")
      step = get_input("step", int, default=100)

      data = parse_data(filename, step=step)
    elif oper == "dp":
      # Print
      print(data)

    # Tree operations
    elif oper == "tb":
      # Build
      try:
        if label in data[0]:
          log = yes_no("log")
          tree = build_tree(data, label, log=log)
        else:
          sys.stderr.write("Label not in data\n")
      except IndexError:
        sys.stderr.write("No data\n")
      except KeyboardInterrupt:
        print("Stopped building tree")
    elif oper == "tp":
      # Print
      if tree:
        print_tree(tree)
      else:
        sys.stderr.write("No tree to print\n")
    elif oper == "ts":
      # Save
      if tree:
        filename = get_input("file", str, default="tree.json")

        try:
          with open(filename, 'w') as f:
            f.write(json.dumps(tree))
            print("Done!")
        except IOError:
          sys.stderr.write("Error while writing file\n")
      else:
        sys.stderr.write("No tree to save\n")
    elif oper == "tl":
      # Load
      filename = get_input("file", str, default="tree.json")

      try:
        with open(filename, 'r') as f:
          tree = json.loads(f.read())
          print("Done!")
      except json.JSONDecodeError:
        sys.stderr.write("Malformed JSON\n")
      except IOError:
        sys.stderr.write("Error while reading file\n")
    elif oper == "tg":
      # Guess
      if tree and data:
        data_point = dict()
        for k, v in data[0].items():
          if k != label:
            data_point[k] = get_input(k, type(v), default=v)

        probs = guess_probability(guess(data_point, tree))
        print('\n'.join([ f"{k}: {v*100:.2f}%" for k,v in probs.items() ]))
      else:
        sys.stderr.write("No tree or data\n")
    else:
      sys.stderr.write("No such operation\n")

if __name__ == '__main__':
  cli()

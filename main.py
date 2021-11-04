#!/usr/bin/env python3

import json
import time

class Question:
  def __init__(self, field, val):
    self.field = field
    self.val = val

  def ask(self, data_point):
    """Compare field from data_point to internal value"""

    val = data_point[self.field]

    if isinstance(val, int) or isinstance(val, float):
      return val >= self.val
    else:
      return val == self.val

  def partition(self, data):
    """Split data according to question"""

    t, f = [], []
    for point in data:
      if self.ask(point):
        t.append(point)
      else:
        f.append(point)

    return t, f

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
    else:
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

  gain, q = calculate_best_partition(data, label_field, log_pad=pad)
  if log: print(pad+"Question done")

  if gain == 0:
    if log: print(pad+"End node")
    # return data
    return count_label(data, label_field)

  t, f = partition(q, data)
  t_branch = build_tree(t, label_field, level=level+1)
  f_branch = build_tree(f, label_field, level=level+1)

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

def main():
  data = []
  with open("data.json", 'r') as f:
    data_raw = json.loads(f.read())
    # TODO: Interpolate co2
    data = [ {
      # Strip microseconds and return only hours
      "time_interval": time.strptime(x["time"][:19], "%Y-%m-%d %H:%M:%S").tm_hour,
      "volume": int(x["volume"]),
      "light": int(x["light"]),
      "temp": float(x["temp"]),
      "humidity": float(x["humidity"]),
    } for x in data_raw[::50] ]

  # Field in data to make a decision tree to find
  label = "time_interval"

  # gain, q = calculate_best_partition(data, label)
  # print(f"{q.field} >= {q.val} ({gain*100:.2f}%)")
  tree = build_tree(data, label)
  print_tree(tree)

if __name__ == '__main__':
  main()

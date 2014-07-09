#!/usr/bin/env python
import os
import argparse
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--gnuplot-filename', default='livedisplay.gnuplot')
parser.add_argument('--data', default='/tmp/livedisplay.dat')
parser.add_argument('--details', default='/tmp/livedisplaydetails.dat')
parser.add_argument('--xrange', type=float, default=300)
parser.add_argument('--yrange', type=float, default=.05)
parser.add_argument('--yrange2', type=float, default=1.0)
parser.add_argument('--remote')
args = parser.parse_args()

if args.remote:
  if os.path.exists(args.data):
    os.unlink(args.data)
  if os.path.exists(args.details):
    os.unlink(args.details)
  syncproc = subprocess.Popen(
      ["ssh", args.remote, "tail -f -n10000 " + args.data],
      stdout=open(args.data, "w"))
  syncproc2 = subprocess.Popen(
      ["ssh", args.remote, "tail -f -n10000 " + args.details],
      stdout=open(args.details, "w"))

while '\n' not in open(args.data).read():
  time.sleep(1)
while '\n' not in open(args.details).read():
  time.sleep(1)

p1 = subprocess.Popen(["gnuplot"], stdin=subprocess.PIPE)
p1.stdin.write(open(args.gnuplot_filename).read())
print >> p1.stdin, 'set title "Zoomed out"'
print >> p1.stdin, "set xrange [0:%f]" % args.xrange
print >> p1.stdin, "set yrange [0:%f]" % args.yrange2
p1.stdin.flush()

time.sleep(1)

p2 = subprocess.Popen(["gnuplot"], stdin=subprocess.PIPE)
p2.stdin.write(open(args.gnuplot_filename).read())
print >> p2.stdin, 'set title "Zoomed in"'
print >> p2.stdin, "set xrange [0:%f]" % args.xrange
print >> p2.stdin, "set yrange [0:%f]" % args.yrange
p2.stdin.flush()

procs = [p1, p2]

while True:
  time.sleep(1)
  for p in procs:
    print >> p.stdin, "replot"
    p.stdin.flush()


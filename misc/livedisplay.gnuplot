
set terminal x11
set xlabel "Autotuning Seconds"
set ylabel "Runtime Seconds"
set xrange [0:300]

plot "/tmp/livedisplay.dat" u 1:2 w lp lw 3 title "Best Execution Time"



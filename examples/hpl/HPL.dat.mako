HPLinpack benchmark input file
Innovative Computing Laboratory, University of Tennessee
HPL.out      output file name (if any)
0            device out (6=stdout,7=stderr,file)
1            # of problems sizes (N)
${size}        Ns
1            # of NBs
${blocksize}		      NBs
${row_or_colmajor_pmapping}            PMAP process mapping (0=Row-,1=Column-major)
1            # of process grids (P x Q)
2	        Ps  PxQ must equal nprocs
2           Qs
16.0         threshold
1            # of panel fact
${pfact}            PFACTs (0=left, 1=Crout, 2=Right)
1            # of recursive stopping criterium
${nbmin}            NBMINs (>= 1)
1            # of panels in recursion
${ndiv}            NDIVs
1            # of recursive panel fact.
${rfact}            RFACTs (0=left, 1=Crout, 2=Right)
1            # of broadcast
${bcast}            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)
1            # of lookahead depth
${depth}            DEPTHs (>=0)
${swap}            SWAP (0=bin-exch,1=long,2=mix)
${swapping_threshold}           swapping threshold (default had 64)
${L1_transposed}            L1 in (0=transposed,1=no-transposed) form
${U_transposed}            U  in (0=transposed,1=no-transposed) form
1            Equilibration (0=no,1=yes)
${mem_alignment}            memory alignment in double (> 0) (4,8,16)

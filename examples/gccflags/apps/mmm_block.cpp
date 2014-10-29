#include <stdio.h>
#include <cstdlib>

int main(int argc, const char** argv)
{
  int BlockSize = atoi(argv[1])*5;
  int n = BlockSize * (n/BlockSize);
  int a[100][100];
  int b[100][100];
  int c[100][100];
  int sum=0;
  for(int k1=0;k1<n;k1+=BlockSize)
  {
      for(int j1=0;j1<n;j1+=BlockSize)
      {
          for(int k1=0;k1<n;k1+=BlockSize)
          {
              for(int i=0;i<n;i++)
              {
                  for(int j=j1;j<j1+BlockSize;j++)
                  {
                      sum = c[i][j];
                      for(int k=k1;k<k1+BlockSize;k++)
                      {               
                          sum += a[i][k] * b[k][j];
                      }
                      c[i][j] = sum;
                  }
              }
          }
      }
         }
  return 0;
}
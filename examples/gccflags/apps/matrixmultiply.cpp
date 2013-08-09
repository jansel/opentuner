// based on: http://blogs.msdn.com/b/xiangfan/archive/2009/04/28/optimize-your-code-matrix-multiplication.aspx
//  by Xiang Fan

#include <algorithm>
#include <iostream>

#define N 512


template<class T>
T** make_test_matrix() {
    T** data = new T*[N];
    for (int i = 0; i < N; i++) {
        data[i] = new T[N];
    }
    for(int i = 0; i < N; i++) {
        for(int j = 0; j < N; j++) {
            data[i][j] = (int) i * j;
        }
    }
    return data;
}



template<typename T>
void Transpose(int size, T** __restrict__ m)
{
    for (int i = 0; i < size; i++) {
        for (int j = i + 1; j < size; j++) {
            std::swap(m[i][j], m[j][i]);
        }
    }
}
template<typename T>
void SeqMatrixMult3(int size, T** __restrict__ m1, T** __restrict__ m2,
                    T** __restrict__ result) {
    Transpose(size, m2);
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            T c = 0;
            for (int k = 0; k < size; k++) {
                c += m1[i][k] * m2[j][k];
            }
            result[i][j] = c;
        }
    }
    Transpose(size, m2);
}


template<typename T>
void test() {
  T** a = make_test_matrix<T>();
  T** b = make_test_matrix<T>();
  T** c = make_test_matrix<T>();
  SeqMatrixMult3(N, a, b, c);


  T avg = 0;
  for(int i = 0; i < N; i++) {
      for(int j = 0; j < N; j++) {
          avg += c[i][j] / (T)(N*N);
      }
  }
  // print out average so caller can check answer
  std::cout << avg << std::endl;
}


int main(int argc, const char** argv) {
  test<float>();
  return 0;
}







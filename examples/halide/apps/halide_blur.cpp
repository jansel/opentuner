#include <Halide.h>
using namespace Halide;

#define AUTOTUNE_HOOK(x)
#define BASELINE_HOOK(x)

int main(int argc, char **argv) {

    ImageParam in_img(UInt(16), 2);
    Func blur_x("blur_x"), blur_y("blur_y");
    Var x("x"), y("y"), xi("xi"), yi("yi");

    Func input;
    input(x,y) = in_img(clamp(x, 1, in_img.width()-1),
                        clamp(y, 1, in_img.height())-1);

    // The algorithm
    blur_x(x, y) = (input(x, y) + input(x+1, y) + input(x+2, y))/3;
    blur_y(x, y) = (blur_x(x, y) + blur_x(x, y+1) + blur_x(x, y+2))/3;

    AUTOTUNE_HOOK(blur_y);

    // How to schedule it
    blur_y.split(y, y, yi, 8).parallel(y).vectorize(x, 8);
    blur_x.store_at(blur_y, y).compute_at(blur_y, yi).vectorize(x, 8);  

    BASELINE_HOOK(blur_y);

    blur_y.compile_to_file("halide_blur", in_img); 

    return 0;
}

/*
	A very basic raytracer example.
	Copyright (C) 2012  www.scratchapixel.com

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.

	- changes 02/04/13: fixed flag in ofstream causing a bug under Windows,
	added default values for M_PI and INFINITY
	- changes 24/05/13: small change to way we compute the refraction direction
	vector (eta=ior if we are inside and 1/ior if we are outside the sphere)

	Compile with the following command: c++ -o raytracer -O3 -Wall raytracer.cpp

*/

#include <cstdlib>
#include <cstdio>
#include <cmath>
#include <fstream>
#include <vector>
#include <iostream>
#include <cassert>

#if defined(__linux__) || defined(__APPLE__)
	// "Compiled for Linux
#else
	// Windows doesn't define these values by default, Linux does
	#define M_PI 3.141592653589793
	#define INFINITY 1e8
#endif

template<typename T>
class Vec3
{
public:
	T x, y, z;
	Vec3() : x(T(0)), y(T(0)), z(T(0)) {}
	Vec3(T xx) : x(xx), y(xx), z(xx) {}
	Vec3(T xx, T yy, T zz) : x(xx), y(yy), z(zz) {}
	Vec3& normalize()
	{
		T nor2 = length2();
		if (nor2 > 0) {
			T invNor = 1 / sqrt(nor2);
			x *= invNor, y *= invNor, z *= invNor;
		}
		return *this;
	}
	Vec3<T> operator * (const T &f) const { return Vec3<T>(x * f, y * f, z * f); }
	Vec3<T> operator * (const Vec3<T> &v) const { return Vec3<T>(x * v.x, y * v.y, z * v.z); }
	T dot(const Vec3<T> &v) const { return x * v.x + y * v.y + z * v.z; }
	Vec3<T> operator - (const Vec3<T> &v) const { return Vec3<T>(x - v.x, y - v.y, z - v.z); }
	Vec3<T> operator + (const Vec3<T> &v) const { return Vec3<T>(x + v.x, y + v.y, z + v.z); }
	Vec3<T>& operator += (const Vec3<T> &v) { x += v.x, y += v.y, z += v.z; return *this; }
	Vec3<T>& operator *= (const Vec3<T> &v) { x *= v.x, y *= v.y, z *= v.z; return *this; }
	Vec3<T> operator - () const { return Vec3<T>(-x, -y, -z); }
	T length2() const { return x * x + y * y + z * z; }
	T length() const { return sqrt(length2()); }
	friend std::ostream & operator << (std::ostream &os, const Vec3<T> &v)
	{
		os << "[" << v.x << " " << v.y << " " << v.z << "]";
		return os;
	}
};

template<typename T>
class Sphere
{
public:
	Vec3<T> center;                         /// position of the sphere
	T radius, radius2;                      /// sphere radius and radius^2
	Vec3<T> surfaceColor, emissionColor;    /// surface color and emission (light)
	T transparency, reflection;             /// surface transparency and reflectivity
	Sphere(const Vec3<T> &c, const T &r, const Vec3<T> &sc, 
		const T &refl = 0, const T &transp = 0, const Vec3<T> &ec = 0) : 
		center(c), radius(r), radius2(r * r), surfaceColor(sc), emissionColor(ec),
		transparency(transp), reflection(refl)
	{}
	// compute a ray-sphere intersection using the geometric solution
	bool intersect(const Vec3<T> &rayorig, const Vec3<T> &raydir, T *t0 = NULL, T *t1 = NULL) const
	{
		Vec3<T> l = center - rayorig;
		T tca = l.dot(raydir);
		if (tca < 0) return false;
		T d2 = l.dot(l) - tca * tca;
		if (d2 > radius2) return false;
		T thc = sqrt(radius2 - d2);
		if (t0 != NULL && t1 != NULL) {
			*t0 = tca - thc;
			*t1 = tca + thc;
		}

		return true;
	}
};

#define MAX_RAY_DEPTH 5

template<typename T>
T mix(const T &a, const T &b, const T &mix)
{
	return b * mix + a * (T(1) - mix);
}

// This is the main trace function. It takes a ray as argument (defined by its origin
// and direction). We test if this ray intersects any of the geometry in the scene.
// If the ray intersects an object, we compute the intersection point, the normal
// at the intersection point, and shade this point using this information.
// Shading depends on the surface property (is it transparent, reflective, diffuse).
// The function returns a color for the ray. If the ray intersects an object that
// is the color of the object at the intersection point, otherwise it returns
// the background color.
template<typename T>
Vec3<T> trace(const Vec3<T> &rayorig, const Vec3<T> &raydir, 
	const std::vector<Sphere<T> *> &spheres, const int &depth)
{
	//if (raydir.length() != 1) std::cerr << "Error " << raydir << std::endl;
	T tnear = INFINITY;
	const Sphere<T> *sphere = NULL;
	// find intersection of this ray with the sphere in the scene
	for (unsigned i = 0; i < spheres.size(); ++i) {
		T t0 = INFINITY, t1 = INFINITY;
		if (spheres[i]->intersect(rayorig, raydir, &t0, &t1)) {
			if (t0 < 0) t0 = t1;
			if (t0 < tnear) {
				tnear = t0;
				sphere = spheres[i];
			}
		}
	}
	// if there's no intersection return black or background color
	if (!sphere) return Vec3<T>(2);
	Vec3<T> surfaceColor = 0; // color of the ray/surfaceof the object intersected by the ray
	Vec3<T> phit = rayorig + raydir * tnear; // point of intersection
	Vec3<T> nhit = phit - sphere->center; // normal at the intersection point
	nhit.normalize(); // normalize normal direction
	// If the normal and the view direction are not opposite to each other 
	// reverse the normal direction. That also means we are inside the sphere so set
	// the inside bool to true. Finally reverse the sign of IdotN which we want
	// positive.
	T bias = 1e-4; // add some bias to the point from which we will be tracing
	bool inside = false;
	if (raydir.dot(nhit) > 0) nhit = -nhit, inside = true;
	if ((sphere->transparency > 0 || sphere->reflection > 0) && depth < MAX_RAY_DEPTH) {
		T facingratio = -raydir.dot(nhit);
		// change the mix value to tweak the effect
		T fresneleffect = mix<T>(pow(1 - facingratio, 3), 1, 0.1); 
		// compute reflection direction (not need to normalize because all vectors
		// are already normalized)
		Vec3<T> refldir = raydir - nhit * 2 * raydir.dot(nhit);
		refldir.normalize();
		Vec3<T> reflection = trace(phit + nhit * bias, refldir, spheres, depth + 1);
		Vec3<T> refraction = 0;
		// if the sphere is also transparent compute refraction ray (transmission)
		if (sphere->transparency) {
			T ior = 1.1, eta = (inside) ? ior : 1 / ior; // are we inside or outside the surface?
			T cosi = -nhit.dot(raydir);
			T k = 1 - eta * eta * (1 - cosi * cosi);
			Vec3<T> refrdir = raydir * eta + nhit * (eta *  cosi - sqrt(k));
			refrdir.normalize();
			refraction = trace(phit - nhit * bias, refrdir, spheres, depth + 1);
		}
		// the result is a mix of reflection and refraction (if the sphere is transparent)
		surfaceColor = (reflection * fresneleffect + 
			refraction * (1 - fresneleffect) * sphere->transparency) * sphere->surfaceColor;
	}
	else {
		// it's a diffuse object, no need to raytrace any further
		for (unsigned i = 0; i < spheres.size(); ++i) {
			if (spheres[i]->emissionColor.x > 0) {
				// this is a light
				Vec3<T> transmission = 1;
				Vec3<T> lightDirection = spheres[i]->center - phit;
				lightDirection.normalize();
				for (unsigned j = 0; j < spheres.size(); ++j) {
					if (i != j) {
						T t0, t1;
						if (spheres[j]->intersect(phit + nhit * bias, lightDirection, &t0, &t1)) {
							transmission = 0;
							break;
						}
					}
				}
				surfaceColor += sphere->surfaceColor * transmission * 
					std::max(T(0), nhit.dot(lightDirection)) * spheres[i]->emissionColor;
			}
		}
	}

	return surfaceColor + sphere->emissionColor;
}

// Main rendering function. We compute a camera ray for each pixel of the image
// trace it and return a color. If the ray hits a sphere, we return the color of the
// sphere at the intersection point, else we return the background color.
template<typename T>
unsigned int render(const std::vector<Sphere<T> *> &spheres)
{
	unsigned width = 640, height = 480;
	Vec3<T> *image = new Vec3<T>[width * height], *pixel = image;
	T invWidth = 1 / T(width), invHeight = 1 / T(height);
	T fov = 30, aspectratio = width / T(height);
	T angle = tan(M_PI * 0.5 * fov / T(180));
	// Trace rays
	for (unsigned y = 0; y < height; ++y) {
		for (unsigned x = 0; x < width; ++x, ++pixel) {
			T xx = (2 * ((x + 0.5) * invWidth) - 1) * angle * aspectratio;
			T yy = (1 - 2 * ((y + 0.5) * invHeight)) * angle;
			Vec3<T> raydir(xx, yy, -1);
			raydir.normalize();
			*pixel = trace(Vec3<T>(0), raydir, spheres, 0);
		}
	}
#if 0
	// Save result to a PPM image (keep these flags if you compile under Windows)
	std::ofstream ofs("./untitled.ppm", std::ios::out | std::ios::binary);
	ofs << "P6\n" << width << " " << height << "\n255\n";
	for (unsigned i = 0; i < width * height; ++i) {
		ofs << (unsigned char)(std::min(T(1), image[i].x) * 255) << 
		(unsigned char)(std::min(T(1), image[i].y) * 255) <<
		(unsigned char)(std::min(T(1), image[i].z) * 255); 
	}
	ofs.close();
#endif

  unsigned int bad_hash = 0;
	for (unsigned i = 0; i < width * height; ++i) {
    bad_hash = bad_hash*31 + (unsigned int)(std::min(T(1), image[i].x) * 255);
    bad_hash = bad_hash*31 + (unsigned int)(std::min(T(1), image[i].y) * 255);
    bad_hash = bad_hash*31 + (unsigned int)(std::min(T(1), image[i].z) * 255);
	}
	delete [] image;

  return bad_hash;
}

volatile unsigned int dont_optimize_me;

int main(int argc, char **argv) {
	srand48(13);
	std::vector<Sphere<float> *> spheres;
	// position, radius, surface color, reflectivity, transparency, emission color
	spheres.push_back(new Sphere<float>(Vec3<float>(0, -10004, -20), 10000, Vec3<float>(0.2), 0, 0.0));
	spheres.push_back(new Sphere<float>(Vec3<float>(0, 0, -20), 4, Vec3<float>(1.00, 0.32, 0.36), 1, 0.5));
	spheres.push_back(new Sphere<float>(Vec3<float>(5, -1, -15), 2, Vec3<float>(0.90, 0.76, 0.46), 1, 0.0));
	spheres.push_back(new Sphere<float>(Vec3<float>(5, 0, -25), 3, Vec3<float>(0.65, 0.77, 0.97), 1, 0.0));
	spheres.push_back(new Sphere<float>(Vec3<float>(-5.5, 0, -15), 3, Vec3<float>(0.90, 0.90, 0.90), 1, 0.0));
	// light
	spheres.push_back(new Sphere<float>(Vec3<float>(0, 20, -30), 3, Vec3<float>(0), 0, 0, Vec3<float>(3)));

  dont_optimize_me = render<float>(spheres);
  __asm__ __volatile__ ("" ::: "memory"); // memory barrier
  if(dont_optimize_me == 0x4bd7c0e0) {
    //printf("CORRECT\n");
  } else {
    printf("ERROR: WRONG ANSWER\n");
  }

	while (!spheres.empty()) {
		Sphere<float> *sph = spheres.back();
		spheres.pop_back();
		delete sph;
	}

	return 0;
}

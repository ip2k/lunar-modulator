/* airwindows_oracle.cc -- the reference renders for Squash and the
 * Limiter's Round mode: the processing loops of four Airwindows plug-ins,
 * in double precision, as upstream writes them (processDoubleReplacing),
 * with only the changes listed at each. Not built by engines/Makefile and
 * not run on a developer's machine: run-on-aeon.sh builds and runs it in a
 * gcc container and writes tests/fixtures/squash-oracle.json from its
 * output (engines/third_party/airwindows/UPSTREAM.md).
 *
 * The loops are copied from Airwindows at commit
 * e718c9bcfcdd736deeddb08bffe6bce2aa8e0eea,
 * plugins/LinuxVST/src/{Pop3,Pressure4,ButterComp2,ClipOnly2}/<name>Proc.cpp:
 *
 *   Copyright (c) 2016 airwindows, Airwindows uses the MIT license
 *   (the licence text: ../LICENSE)
 *
 * Changes from upstream, for all four: the plug-in state is a struct, the
 * knobs A..H are arguments, the sample rate is 44,100 Hz (overallscale 1),
 * and every source of noise is removed (the fpd denormal dither on input,
 * the floating-point dither on output, ButterComp2's "live air" residue),
 * so the oracle is deterministic and silence gives silence. For Pressure4
 * also: the output sine stage is removed and the 1/threshold lift is divided
 * out at the end (Squash's Mu, engines/src/fx_squash.cc), with Output Gain D
 * at 1.
 *
 * Usage: airwindows_oracle KIND A B C D E F G H < in.f32 > out.f32, where
 * KIND is pop3, pressure4, buttercomp2 or clip, and the files are
 * interleaved stereo float32, little-endian. Unused knobs are ignored.
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vector>

namespace {

void Pop3(std::vector<double> &io, const double *k) {
  const double A = k[0], B = k[1], C = k[2], D = k[3], E = k[4], F = k[5], G = k[6], H = k[7];
  double popCompL = 1.0, popCompR = 1.0, popGate = 1.0;
  double overallscale = 1.0;
  double compThresh = pow(A,4);
  double compRatio = 1.0-pow(1.0-B,2);
  double compAttack = 1.0/(((pow(C,3)*5000.0)+500.0)*overallscale);
  double compRelease = 1.0/(((pow(D,5)*50000.0)+500.0)*overallscale);
  double gateThresh = pow(E,4);
  double gateRatio = 1.0-pow(1.0-F,2);
  double gateSustain = M_PI_2 * pow(G+1.0,4.0);
  double gateRelease = 1.0/(((pow(H,5)*500000.0)+500.0)*overallscale);
  for (size_t i = 0; i < io.size(); i += 2) {
    double inputSampleL = io[i];
    double inputSampleR = io[i + 1];
    if (fabs(inputSampleL) > compThresh) { //compression L
      popCompL -= (popCompL * compAttack);
      popCompL += ((compThresh / fabs(inputSampleL))*compAttack);
    } else popCompL = (popCompL*(1.0-compRelease))+compRelease;
    if (fabs(inputSampleR) > compThresh) { //compression R
      popCompR -= (popCompR * compAttack);
      popCompR += ((compThresh / fabs(inputSampleR))*compAttack);
    } else popCompR = (popCompR*(1.0-compRelease))+compRelease;
    if (popCompL > popCompR) popCompL -= (popCompL * compAttack);
    if (popCompR > popCompL) popCompR -= (popCompR * compAttack);
    if (fabs(inputSampleL) > gateThresh) popGate = gateSustain;
    else if (fabs(inputSampleR) > gateThresh) popGate = gateSustain;
    else popGate *= (1.0-gateRelease);
    if (popGate < 0.0) popGate = 0.0;
    popCompL = fmax(fmin(popCompL,1.0),0.0);
    popCompR = fmax(fmin(popCompR,1.0),0.0);
    inputSampleL *= ((1.0-compRatio)+(popCompL*compRatio));
    inputSampleR *= ((1.0-compRatio)+(popCompR*compRatio));
    if (popGate < M_PI_2) {
      inputSampleL *= ((1.0-gateRatio)+(sin(popGate)*gateRatio));
      inputSampleR *= ((1.0-gateRatio)+(sin(popGate)*gateRatio));
    }
    io[i] = inputSampleL;
    io[i + 1] = inputSampleR;
  }
}

void Pressure4(std::vector<double> &io, const double *k) {
  const double A = k[0], B = k[1], C = k[2], D = 1.0;
  double muSpeedA = 10000, muSpeedB = 10000, muCoefficientA = 1, muCoefficientB = 1;
  double muVary = 1, muAttack, muNewSpeed;
  bool flip = false;
  double overallscale = 1.0;
  double threshold = 1.0 - (A * 0.95);
  double muMakeupGain = 1.0 / threshold;
  double release = pow((1.28-B),5)*32768.0;
  release /= overallscale;
  double fastest = sqrt(release);
  double coefficient;
  double inputSense;
  double mewiness = (C*2.0)-1.0;
  double unmewiness;
  double outputGain = D;
  bool positivemu;
  if (mewiness >= 0) { positivemu = true; unmewiness = 1.0-mewiness; }
  else { positivemu = false; mewiness = -mewiness; unmewiness = 1.0-mewiness; }
  for (size_t i = 0; i < io.size(); i += 2) {
    double inputSampleL = io[i];
    double inputSampleR = io[i + 1];
    inputSampleL = inputSampleL * muMakeupGain;
    inputSampleR = inputSampleR * muMakeupGain;
    inputSense = fabs(inputSampleL);
    if (fabs(inputSampleR) > inputSense) inputSense = fabs(inputSampleR);
    if (flip) {
      if (inputSense > threshold) {
        muVary = threshold / inputSense;
        muAttack = sqrt(fabs(muSpeedA));
        muCoefficientA = muCoefficientA * (muAttack-1.0);
        if (muVary < threshold) muCoefficientA = muCoefficientA + threshold;
        else muCoefficientA = muCoefficientA + muVary;
        muCoefficientA = muCoefficientA / muAttack;
      } else {
        muCoefficientA = muCoefficientA * ((muSpeedA * muSpeedA)-1.0);
        muCoefficientA = muCoefficientA + 1.0;
        muCoefficientA = muCoefficientA / (muSpeedA * muSpeedA);
      }
      muNewSpeed = muSpeedA * (muSpeedA-1);
      muNewSpeed = muNewSpeed + fabs(inputSense*release)+fastest;
      muSpeedA = muNewSpeed / muSpeedA;
    } else {
      if (inputSense > threshold) {
        muVary = threshold / inputSense;
        muAttack = sqrt(fabs(muSpeedB));
        muCoefficientB = muCoefficientB * (muAttack-1);
        if (muVary < threshold) muCoefficientB = muCoefficientB + threshold;
        else muCoefficientB = muCoefficientB + muVary;
        muCoefficientB = muCoefficientB / muAttack;
      } else {
        muCoefficientB = muCoefficientB * ((muSpeedB * muSpeedB)-1.0);
        muCoefficientB = muCoefficientB + 1.0;
        muCoefficientB = muCoefficientB / (muSpeedB * muSpeedB);
      }
      muNewSpeed = muSpeedB * (muSpeedB-1);
      muNewSpeed = muNewSpeed + fabs(inputSense*release)+fastest;
      muSpeedB = muNewSpeed / muSpeedB;
    }
    if (flip) {
      if (positivemu) coefficient = pow(muCoefficientA,2);
      else coefficient = sqrt(muCoefficientA);
      coefficient = (coefficient*mewiness)+(muCoefficientA*unmewiness);
      inputSampleL *= coefficient;
      inputSampleR *= coefficient;
    } else {
      if (positivemu) coefficient = pow(muCoefficientB,2);
      else coefficient = sqrt(muCoefficientB);
      coefficient = (coefficient*mewiness)+(muCoefficientB*unmewiness);
      inputSampleL *= coefficient;
      inputSampleR *= coefficient;
    }
    if (outputGain != 1.0) {
      inputSampleL *= outputGain;
      inputSampleR *= outputGain;
    }
    // Upstream's sine output stage is removed here, and the lift divided out:
    io[i] = inputSampleL * threshold;
    io[i + 1] = inputSampleR * threshold;
  }
}

void ButterComp2(std::vector<double> &io, const double *k) {
  const double A = k[0], B = k[1], C = k[2];
  double controlAposL = 1.0, controlAnegL = 1.0, controlBposL = 1.0, controlBnegL = 1.0;
  double targetposL = 1.0, targetnegL = 1.0, lastOutputL = 0.0;
  double controlAposR = 1.0, controlAnegR = 1.0, controlBposR = 1.0, controlBnegR = 1.0;
  double targetposR = 1.0, targetnegR = 1.0, lastOutputR = 0.0;
  bool flip = false;
  double overallscale = 1.0;
  double inputgain = pow(10.0,(A*14.0)/20.0);
  double compfactor = 0.012 * (A / 135.0);
  double output = B * 2.0;
  double wet = C;
  double outputgain = inputgain;
  outputgain -= 1.0;
  outputgain /= 1.5;
  outputgain += 1.0;
  for (size_t i = 0; i < io.size(); i += 2) {
    double inputSampleL = io[i];
    double inputSampleR = io[i + 1];
    // The "live air" residue (function-static noise) is removed here.
    double drySampleL = inputSampleL;
    double drySampleR = inputSampleR;
    inputSampleL *= inputgain;
    inputSampleR *= inputgain;
    double divisor = compfactor / (1.0+fabs(lastOutputL));
    divisor /= overallscale;
    double remainder = divisor;
    divisor = 1.0 - divisor;
    double inputposL = inputSampleL + 1.0;
    if (inputposL < 0.0) inputposL = 0.0;
    double outputposL = inputposL / 2.0;
    if (outputposL > 1.0) outputposL = 1.0;
    inputposL *= inputposL;
    targetposL *= divisor;
    targetposL += (inputposL * remainder);
    double calcposL = pow((1.0/targetposL),2);
    double inputnegL = (-inputSampleL) + 1.0;
    if (inputnegL < 0.0) inputnegL = 0.0;
    double outputnegL = inputnegL / 2.0;
    if (outputnegL > 1.0) outputnegL = 1.0;
    inputnegL *= inputnegL;
    targetnegL *= divisor;
    targetnegL += (inputnegL * remainder);
    double calcnegL = pow((1.0/targetnegL),2);
    if (inputSampleL > 0) {
      if (flip) { controlAposL *= divisor; controlAposL += (calcposL*remainder); }
      else { controlBposL *= divisor; controlBposL += (calcposL*remainder); }
    } else {
      if (flip) { controlAnegL *= divisor; controlAnegL += (calcnegL*remainder); }
      else { controlBnegL *= divisor; controlBnegL += (calcnegL*remainder); }
    }
    divisor = compfactor / (1.0+fabs(lastOutputR));
    divisor /= overallscale;
    remainder = divisor;
    divisor = 1.0 - divisor;
    double inputposR = inputSampleR + 1.0;
    if (inputposR < 0.0) inputposR = 0.0;
    double outputposR = inputposR / 2.0;
    if (outputposR > 1.0) outputposR = 1.0;
    inputposR *= inputposR;
    targetposR *= divisor;
    targetposR += (inputposR * remainder);
    double calcposR = pow((1.0/targetposR),2);
    double inputnegR = (-inputSampleR) + 1.0;
    if (inputnegR < 0.0) inputnegR = 0.0;
    double outputnegR = inputnegR / 2.0;
    if (outputnegR > 1.0) outputnegR = 1.0;
    inputnegR *= inputnegR;
    targetnegR *= divisor;
    targetnegR += (inputnegR * remainder);
    double calcnegR = pow((1.0/targetnegR),2);
    if (inputSampleR > 0) {
      if (flip) { controlAposR *= divisor; controlAposR += (calcposR*remainder); }
      else { controlBposR *= divisor; controlBposR += (calcposR*remainder); }
    } else {
      if (flip) { controlAnegR *= divisor; controlAnegR += (calcnegR*remainder); }
      else { controlBnegR *= divisor; controlBnegR += (calcnegR*remainder); }
    }
    double totalmultiplierL;
    double totalmultiplierR;
    if (flip) {
      totalmultiplierL = (controlAposL * outputposL) + (controlAnegL * outputnegL);
      totalmultiplierR = (controlAposR * outputposR) + (controlAnegR * outputnegR);
    } else {
      totalmultiplierL = (controlBposL * outputposL) + (controlBnegL * outputnegL);
      totalmultiplierR = (controlBposR * outputposR) + (controlBnegR * outputnegR);
    }
    inputSampleL *= totalmultiplierL;
    inputSampleL /= outputgain;
    inputSampleR *= totalmultiplierR;
    inputSampleR /= outputgain;
    if (output != 1.0) {
      inputSampleL *= output;
      inputSampleR *= output;
    }
    if (wet !=1.0) {
      inputSampleL = (inputSampleL * wet) + (drySampleL * (1.0-wet));
      inputSampleR = (inputSampleR * wet) + (drySampleR * (1.0-wet));
    }
    lastOutputL = inputSampleL;
    lastOutputR = inputSampleR;
    flip = !flip;
    io[i] = inputSampleL;
    io[i + 1] = inputSampleR;
  }
}

void ClipOnly2(std::vector<double> &io) {
  double lastSampleL = 0.0, lastSampleR = 0.0;
  double intermediateL[16], intermediateR[16];
  bool wasPosClipL = false, wasNegClipL = false, wasPosClipR = false, wasNegClipR = false;
  for (int x = 0; x < 16; x++) { intermediateL[x] = 0.0; intermediateR[x] = 0.0; }
  double overallscale = 1.0;
  int spacing = floor(overallscale);
  if (spacing < 1) spacing = 1; if (spacing > 16) spacing = 16;
  for (size_t i = 0; i < io.size(); i += 2) {
    double inputSampleL = io[i];
    double inputSampleR = io[i + 1];
    if (inputSampleL > 4.0) inputSampleL = 4.0; if (inputSampleL < -4.0) inputSampleL = -4.0;
    if (wasPosClipL == true) {
      if (inputSampleL<lastSampleL) lastSampleL=0.7058208+(inputSampleL*0.2609148);
      else lastSampleL = 0.2491717+(lastSampleL*0.7390851);
    } wasPosClipL = false;
    if (inputSampleL>0.9549925859) {wasPosClipL=true;inputSampleL=0.7058208+(lastSampleL*0.2609148);}
    if (wasNegClipL == true) {
      if (inputSampleL > lastSampleL) lastSampleL=-0.7058208+(inputSampleL*0.2609148);
      else lastSampleL=-0.2491717+(lastSampleL*0.7390851);
    } wasNegClipL = false;
    if (inputSampleL<-0.9549925859) {wasNegClipL=true;inputSampleL=-0.7058208+(lastSampleL*0.2609148);}
    intermediateL[spacing] = inputSampleL;
    inputSampleL = lastSampleL;
    for (int x = spacing; x > 0; x--) intermediateL[x-1] = intermediateL[x];
    lastSampleL = intermediateL[0];
    if (inputSampleR > 4.0) inputSampleR = 4.0; if (inputSampleR < -4.0) inputSampleR = -4.0;
    if (wasPosClipR == true) {
      if (inputSampleR<lastSampleR) lastSampleR=0.7058208+(inputSampleR*0.2609148);
      else lastSampleR = 0.2491717+(lastSampleR*0.7390851);
    } wasPosClipR = false;
    if (inputSampleR>0.9549925859) {wasPosClipR=true;inputSampleR=0.7058208+(lastSampleR*0.2609148);}
    if (wasNegClipR == true) {
      if (inputSampleR > lastSampleR) lastSampleR=-0.7058208+(inputSampleR*0.2609148);
      else lastSampleR=-0.2491717+(lastSampleR*0.7390851);
    } wasNegClipR = false;
    if (inputSampleR<-0.9549925859) {wasNegClipR=true;inputSampleR=-0.7058208+(lastSampleR*0.2609148);}
    intermediateR[spacing] = inputSampleR;
    inputSampleR = lastSampleR;
    for (int x = spacing; x > 0; x--) intermediateR[x-1] = intermediateR[x];
    lastSampleR = intermediateR[0];
    io[i] = inputSampleL;
    io[i + 1] = inputSampleR;
  }
}

}  // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s pop3|pressure4|buttercomp2|clip A B C D E F G H < in > out\n", argv[0]);
    return 2;
  }
  double k[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
  for (int i = 0; i < 8 && i + 2 < argc; ++i) k[i] = atof(argv[i + 2]);
  std::vector<float> in;
  float buf[4096];
  size_t n;
  while ((n = fread(buf, sizeof(float), 4096, stdin)) > 0) in.insert(in.end(), buf, buf + n);
  std::vector<double> io(in.begin(), in.end());
  if (strcmp(argv[1], "pop3") == 0) Pop3(io, k);
  else if (strcmp(argv[1], "pressure4") == 0) Pressure4(io, k);
  else if (strcmp(argv[1], "buttercomp2") == 0) ButterComp2(io, k);
  else if (strcmp(argv[1], "clip") == 0) ClipOnly2(io);
  else return 2;
  std::vector<float> out(io.begin(), io.end());
  fwrite(out.data(), sizeof(float), out.size(), stdout);
  return 0;
}

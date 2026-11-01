/* SPDX-License-Identifier: MIT. Shared C/assembly OFFLINE selection guards. */
#if !defined(LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE) || LUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE != 1 || !defined(LUNAR_CPU1_CANDIDATE_STOCK_SPL) || LUNAR_CPU1_CANDIDATE_STOCK_SPL != 1
#error This separate offline profile requires candidate=1 and stock-SPL=1
#endif
#if !defined(__PI32V2__) || __PI32V2__ != 1 || !defined(LUNAR_CPU1_CANDIDATE_PI32V2) || LUNAR_CPU1_CANDIDATE_PI32V2 != 1 || defined(LUNAR_CPU1_CANDIDATE_HOST) || defined(__unix__) || defined(__APPLE__) || defined(_WIN32) || defined(__arm__) || defined(__aarch64__) || defined(__x86_64__) || defined(__i386__) || defined(__riscv) || defined(__wasm__)
#error Offline target hooks require the explicitly selected pi32v2 target
#endif
#if defined(LUNAR_NATIVE_PIPELINE_ENABLE) && LUNAR_NATIVE_PIPELINE_ENABLE
#error Production CPU1 execution has not been admitted
#endif

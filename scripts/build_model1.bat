@echo off
set "PATH=C:\msys64\ucrt64\bin;C:\msys64\usr\bin;%PATH%"
set "MINGW64=C:/msys64/ucrt64"
C:\msys64\usr\bin\make.exe SUBTARGET=model1 SOURCES=src/mame/sega/model1.cpp PTR64=1 -j16

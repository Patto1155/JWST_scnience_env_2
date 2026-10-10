"""Bounded, publisher-verified acquisition and build of complete Cloudy C23.01."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes.util
import hashlib
import json
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

URL = "https://data.nublado.org/cloudy_releases/c23/c23.01.tar.gz"
DOI = "https://doi.org/10.5281/zenodo.14142065"
ARCHIVE_BYTES = 338434070
ARCHIVE_MD5 = "73917420ab471497fa15750c751bbf1f"
ARCHIVE_SHA256 = "a9ad2dc037e88f552389de0e483d68f54310976dee32154ed13830882aedae0b"
CHUNK_BYTES = 4 * 1024**2


def verify(path: Path) -> dict:
    if path.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("Cloudy archive length differs from publisher pin")
    data = path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    if hashlib.md5(data).hexdigest() != ARCHIVE_MD5 or sha256 != ARCHIVE_SHA256:
        raise ValueError("Cloudy archive differs from independently frozen publisher pins")
    return {"url": URL, "doi": DOI, "bytes": len(data), "md5": ARCHIVE_MD5, "sha256": sha256}


def acquire(root: Path, workers: int = 8) -> dict:
    """HTTP ranges validate status, extent, exact payload, whole-archive pins."""
    if not 1 <= workers <= 12:
        raise ValueError("bounded worker count required")
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "c23.01.tar.gz"
    if archive.exists() and archive.stat().st_size == ARCHIVE_BYTES:
        return verify(archive)
    transferred = 0
    started = time.monotonic()

    def get(index: int) -> tuple[int, int]:
        part = root / f"part{index:03}"
        start = index * CHUNK_BYTES
        end = min(ARCHIVE_BYTES, start + CHUNK_BYTES) - 1
        if part.exists() and part.stat().st_size == end - start + 1:
            return index, 0
        request = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status != 206 or response.headers.get("Content-Range") != (
                f"bytes {start}-{end}/{ARCHIVE_BYTES}"
            ):
                raise ValueError("publisher range identity differs")
            payload = response.read(end - start + 2)
        if len(payload) != end - start + 1:
            raise ValueError("publisher range length differs")
        part.write_bytes(payload)
        return index, len(payload)

    count = (ARCHIVE_BYTES + CHUNK_BYTES - 1) // CHUNK_BYTES
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for _, size in executor.map(get, range(count)):
            transferred += size
    temporary = root / "c23.01.tar.gz.partial"
    with temporary.open("wb") as output:
        for index in range(count):
            output.write((root / f"part{index:03}").read_bytes())
    receipt = verify(temporary)
    temporary.replace(archive)
    receipt.update(
        transferred_bytes_this_execution=transferred, acquisition_seconds=time.monotonic() - started
    )
    return receipt


def unpack_build(
    root: Path, jobs: int = 2, system_lapack: bool = False, scipy_openblas: bool = False
) -> dict:
    """Trusted operator build; does not expose code execution to research workers."""
    if not 1 <= jobs <= 4:
        raise ValueError("bounded compilation parallelism required")
    if system_lapack and scipy_openblas:
        raise ValueError("choose one external LP64 backend")
    receipt = verify(root / "c23.01.tar.gz")
    source = root / "c23.01"
    if not source.exists():
        with tarfile.open(root / "c23.01.tar.gz") as archive:
            archive.extractall(root, filter="data")
    build_dir = source / "source" / "sys_pilot"
    build_dir.mkdir(exist_ok=True)
    (build_dir / "Makefile").write_bytes((source / "source" / "sys_gcc" / "Makefile").read_bytes())
    configuration = (
        "OPT = -O1 -ftrapping-math -fno-math-errno -Wno-deprecated-declarations\n"
        "CXXFLAGS = $(STD) $(OPT) -Wall -W\nLDFLAGS = $(OPT) -Wall\n"
    )
    (build_dir / "Makefile.conf").write_text(configuration)
    started = time.monotonic()
    result = subprocess.run(
        ["make", f"-j{jobs}"],
        cwd=build_dir,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    (root / "build.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError("Cloudy build failed; inspect external build.log")
    executable = build_dir / "cloudy.exe"
    if system_lapack or scipy_openblas:
        library_directory = None
        if scipy_openblas:
            import scipy

            library_directory = Path(scipy.__file__).resolve().parent.parent / "scipy.libs"
            libraries = list(library_directory.glob("libscipy_openblas-*.so"))
            if len(libraries) != 1:
                raise ValueError("one already installed SciPy LP64 OpenBLAS required")
            library = libraries[0].name
        else:
            library = ctypes.util.find_library("lapack")
        if not library:
            raise ValueError("existing system LAPACK requested but unavailable")
        wrapper = build_dir / "thirdparty_lapack_external.o"
        compile_args = [
            "g++",
            "-std=c++11",
            "-O2",
            "-ftrapping-math",
            "-fno-math-errno",
            "-Wno-deprecated-declarations",
            "-DLAPACK",
            "-no-pie",
            "-fno-pie",
            f'-DSYS_CONFIG="{build_dir / "cloudyconfig.h"}"',
            "-c",
            "../thirdparty_lapack.cpp",
            "-o",
            wrapper.name,
        ]
        if scipy_openblas:
            compile_args[1:1] = [
                "-Ddgetrf_=scipy_dgetrf_",
                "-Ddgetrs_=scipy_dgetrs_",
                "-Ddgtsv_=scipy_dgtsv_",
            ]
        subprocess.run(compile_args, cwd=build_dir, check=True, timeout=120)
        executable = build_dir / ("cloudy-openblas.exe" if scipy_openblas else "cloudy-lapack.exe")
        link_args = [
            "g++",
            "-O2",
            "-no-pie",
            "-fno-pie",
            "-Wl,-export-dynamic",
            "-o",
            executable.name,
            "maincl.o",
            wrapper.name,
            "-L.",
            "-lcloudy",
            f"-l:{library}",
        ]
        if library_directory:
            link_args[-1:-1] = [f"-L{library_directory}", f"-Wl,-rpath,{library_directory}"]
        subprocess.run(link_args, cwd=build_dir, check=True, timeout=120)
        receipt["lapack_backend"] = {
            "library": library,
            "compile_args": compile_args,
            "link_args": link_args,
            "dynamic_links": subprocess.check_output(["ldd", str(executable)], text=True),
            "integer_ABI": "LP64 int32, as declared by publisher wrapper",
            "symbol_namespace_aliases": [
                "dgetrf_->scipy_dgetrf_",
                "dgetrs_->scipy_dgetrs_",
                "dgtsv_->scipy_dgtsv_",
            ]
            if scipy_openblas
            else [],
        }
        if library_directory:
            receipt["lapack_backend"]["existing_libraries"] = [
                {
                    "name": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(library_directory.glob("*.so*"))
            ]
    receipt.update(
        build_seconds=time.monotonic() - started,
        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        makefile_config=configuration,
        compiler=subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--system-lapack", action="store_true")
    parser.add_argument("--scipy-openblas", action="store_true")
    args = parser.parse_args()
    receipt = acquire(args.directory)
    if args.build:
        receipt["build"] = unpack_build(
            args.directory,
            jobs=4,
            system_lapack=args.system_lapack,
            scipy_openblas=args.scipy_openblas,
        )
    (args.directory / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

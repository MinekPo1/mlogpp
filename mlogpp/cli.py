import argparse
import os
import sys
import enum

import pyperclip

from .lexer import Lexer, Lexer
from .preprocess import Preprocessor
from .parser_rewrite import Parser
from .optimizer import Optimizer
from .linker import Linker
from .error import MlogError
from .compile import compile_code
from . import __version__


# input/output method
class IOMethod(enum.Enum):
    FILE = enum.auto()
    STD = enum.auto()
    CLIP = enum.auto()


def main():
    parser = argparse.ArgumentParser(description="Mindustry logic compiler", prog="mlog++")

    parser.add_argument("file", type=str, help="input file [@clip for clipboard]")

    parser.add_argument("-o:f", "--output-file", help="write output to a file")
    parser.add_argument("-o:s", "--output-stdout", help="write output to stdout", action="store_true")
    parser.add_argument("-o:c", "--output-clip", help="write output to clipboard (default)", action="store_true")

    parser.add_argument("-v", "--verbose", help="print additional information", action="store_true")
    parser.add_argument("-l", "--lines", help="print line numbers when output to stdout is selected", action="store_true")

    parser.add_argument("--print-exceptions", help="print all exceptions from the compilation (development only)", action="store_true")

    parser.add_argument("-V", "--version", action="version", version=f"mlog++ {__version__}")

    args = parser.parse_args()

    output_method = IOMethod.CLIP
    output_file = ""

    verbose = False

    # parse arguments
    for k, v in vars(args).items():
        if v:
            if k.startswith("output"):
                # output method

                output_method = IOMethod.FILE if k.endswith("file") else IOMethod.STD if k.endswith("stdout") else IOMethod.CLIP
                if output_method == IOMethod.FILE:
                    output_file = v

            elif k == "verbose":
                # verbose

                verbose = v

    # check if input file exists
    if not os.path.isfile(args.file) and args.file != "@clip":
        print(f"Error: input file \"{args.file}\" does not exist")
        sys.exit(1)

    if args.file == "@clip":
        code = pyperclip.paste()
    else:
        with open(args.file, "r") as f:
            code = f.read()

    try:
        out = compile_code(code, args.file)
    except MlogError as e:
        e.print()
        if args.print_exceptions:
            raise e
        sys.exit(1)

    if output_method == IOMethod.FILE:
        # output to file

        with open(output_file, "w+") as f:
            f.write(out)

    elif output_method == IOMethod.STD:
        # output to stdout

        # check if line numbers should be printed
        if vars(args)["lines"]:
            lines = out.splitlines()
            max_line = len(str(len(lines)))
            for i, ln in enumerate(lines):
                print(f"{str(i).zfill(max_line)}: {ln}")
        else:
            print(out)

        if verbose:
            print()

    elif output_method == IOMethod.CLIP:
        # output to clipboard

        pyperclip.copy(out)

    if verbose:
        print(f"Output: {len(out.strip())} characters, {len(out.strip().split())} words, {len(out.strip().splitlines())} lines")

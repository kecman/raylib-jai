'''

naive regex-based code for turning raylib.h into raylib.jai

'''
import re
import os.path
from io import StringIO

ctx = dict()

def p(*a, **k):
    # a shortcut for printing to the output file
    if "file" not in k and "output_file" in ctx:
        k["file"] = ctx["output_file"]
    print(*a, **k)

type_replacements = [
    ("const char", "u8"),
    ("const ", ""),
    ("unsigned short", "u16"),
    ("unsigned int", "u32"),
    ("unsigned char", "u8"),
    ("char", "s8"),
    ("long", "s32"),
    ("double", "float64"),
    ("int", "s32"),
]

def replace_types(s):
    for c_type, jai_type in type_replacements:
        s = re.sub(r"\b" + c_type + r"\b", jai_type, s)
    return s

def generate_jai_bindings():
    header = open("raylib/include/raylib.h").read()
    native_lib_name = "raylib_native"
    path_to_native_lib = "raylib/lib/raylib"

    ctx["output_file"] = open("raylib.jai", "w")
    with ctx["output_file"]:

        p("//\n// AUTOGENERATED\n//\n")

        #
        # colors
        #
        for match in re.finditer(r"#define (\w+)\s+CLITERAL\(Color\){([^}]+)}", header):
            color_name = match.group(1)
            values = match.group(2)
            p(f"{color_name} :: Color.{{ {values} }};")

        #
        #  function pointers aren't parsed by regexes yet, so this is the only thing "by hand"
        #
        p("\nTraceLogCallback :: #type (logType: s32, text: *u8, args: ..*u8);\n")

        #
        # enums
        #
        for match in re.finditer(r"typedef enum {([^}]*)} (\w+);", header):
            enum_id = match.group(2)
            if enum_id == "bool":
                continue # skip the C compat bool definition

            enum_contents = match.group(1).strip()\
                .replace("=", "::")\
                .replace(",", ";")

            enum_contents = re.sub(r"//.*$", "", enum_contents)
            # TODO: the above removes the last comment in an enum body...we could probably retain them

            if not enum_contents.endswith(";"):
                enum_contents = enum_contents.rstrip() + ";"

            p(f"{enum_id} :: enum {{\n    {enum_contents}\n}}\n")

        #
        # aliases
        #
        for match in re.finditer(r"typedef struct (\w+) (\w+);", header):
            struct_id = match.group(2)
            p(f"{struct_id} :: struct {{ /* only used as a pointer in this header */ }}\n")
        
        for match in re.finditer(r"typedef (\w+) (\w+);", header):
            if match.group(1) == "struct":
                continue # handled by loop above
            
            aliased_struct = match.group(1)
            struct_id = match.group(2)

            p(f"{struct_id} :: {aliased_struct};\n")

        #
        # structs
        #
        for match in re.finditer(r"typedef struct (\w+) {([^}]*)}", header):
            identifier = match.group(1)

            struct_contents = StringIO()
            for line in replace_types(match.group(2).strip()).split("\n"):
                field_m = re.search(r"(.*?)((\w+|, )+)(\[\d+\])?;", line)
                if field_m is None: continue

                field_type = replace_types(field_m.group(1).strip())
                pointer_count = 0
                if field_type.endswith(" **"):
                    pointer_count = 2
                    field_type = field_type[:-3]
                if field_type.endswith(" *"):
                    pointer_count = 1
                    field_type = field_type[:-2]
                field_id = field_m.group(2).strip()

                pointer_char = "*" * pointer_count

                p(f"    {field_id}: {pointer_char}{field_type};", file=struct_contents)
            
            p(f"{identifier} :: struct {{\n{struct_contents.getvalue()}}}\n")
        
        #
        # functions
        #
        for match in re.finditer(r"RLAPI (.*?)(\w+)\(([^\)]*)\);", header):
            return_type = match.group(1).strip()
            func_name = match.group(2)
            args = match.group(3)

            arg_contents = StringIO()
            if args != "void":
                for arg in args.split(","):
                    tokens = arg.strip().split(" ")
                    arg_name = tokens[-1]
                    arg_type = replace_types(" ".join(tokens[:-1]))
                    pointer_count = 0
                    if arg_name.startswith("**"):
                        pointer_count = 2
                        arg_name = arg_name[2:]
                    if arg_name.startswith("*"):
                        pointer_count = 1
                        arg_name = arg_name[1:]
                    pointer_char = "*" * pointer_count

                    if arg_name == "...":
                        p(f"args: ..*u8", file=arg_contents, end="")
                    else:
                        p(f"{arg_name}: {pointer_char}{arg_type}, ", file=arg_contents, end="")

            arg_contents = arg_contents.getvalue()
            if arg_contents.endswith(", "):
                arg_contents = arg_contents[:-2]
            
            if return_type == "void":
                return_type_string = ""
            else:
                return_type = replace_types(return_type)
                if return_type.endswith(" **"):
                    return_type = "**" + return_type[:-3]
                elif return_type.endswith(" *"):
                    return_type = "*" + return_type[:-2]

                return_type_string = "-> " + return_type

            p(f"{func_name} :: ({arg_contents}) {return_type_string} #foreign {native_lib_name} \"{func_name}\";")
        
        #
        # native library
        #
        p("\n#scope_file // ---------------\n")
        p("#if OS == .WINDOWS {")
        p("""    #foreign_system_library "user32";""")
        p("""    #foreign_system_library "gdi32";""")
        p("""    #foreign_system_library "shell32";""")
        p("""    #foreign_system_library "winmm";""")
        p(f"    {native_lib_name} :: #foreign_library,no_dll \"{path_to_native_lib}\";")
        p("}")


def main():
    # change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    generate_jai_bindings()

if __name__ == "__main__":
    main()

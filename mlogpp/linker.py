from .instruction import *
from .expression import Expression


class Linker:
    """
    Resolves labels.
    """

    @staticmethod
    def link(code: Instructions | Instruction) -> str:
        """
        Resolve labels.

        Args:
            code: The generated instructions.

        Returns:
            The code with resolved labels.
        """

        # label at the start of the code
        labels = {"start": 0}
        macros: dict[str, str] = {}

        # find labels and process macros

        instrs: list[str] = []
        for ins in code.iter():
            if isinstance(ins, MppInstructionLabel):
                labels[ins.name] = len(instrs)
                continue
            
            if isinstance(ins, MppInstructionMacro):
                if ins.value.startswith(":"):
                    Expression.variables["here_ptr"] = len(instrs)
                    Expression.variables["labels"] = labels
                    Expression.variables["macros"] = macros
                    val = Expression.exec(ins.pos, ins.value.removeprefix(":"))

                    if isinstance(val, list):
                        val = " ".join(str(i) for i in val)
                    else:
                        val = str(val)

                else:
                    val = ins.value
                macros[ins.name] = val
                continue

            if not str(ins):
                continue

            instrs.append(" ".join( macros.get(i, i) for i in str(ins).split() ))

        output_code = "\n".join(" ".join(str(labels.get(word, word)) for word in line.split()) for line in instrs)

        return output_code.strip()

"""Small independent evaluator for the scalar Excel formulas generated here.

This is test infrastructure, not a spreadsheet engine or proof of Excel UI behavior.
Unknown syntax fails explicitly; cycles fail instead of using cached cell values.
"""
import ast
import operator
import re


class Evaluator:
    def __init__(self,workbook):
        self.workbook=workbook
        self.cache={}
        self.visiting=set()

    def cell(self,sheet,address):
        key=(sheet,address.replace("$",""))
        if key in self.cache:
            return self.cache[key]
        if key in self.visiting:
            raise AssertionError(f"Circular reference: {key}")
        self.visiting.add(key)
        value=self.workbook[sheet][key[1]].value
        if isinstance(value,str) and value.startswith("="):
            expr=value[1:]
            refs=[]
            def replacement(match):
                refs.append((match.group(1) or sheet,match.group(2)))
                return f"REF({len(refs)-1})"
            expr=re.sub(r"(?:'([^']+)'!)?(\$?[A-Z]{1,3}\$?\d+)",replacement,expr)
            expr=expr.replace("^","**")
            value=self.evaluate(ast.parse(expr,mode="eval").body,refs)
        self.visiting.remove(key)
        self.cache[key]=value
        return value

    def evaluate(self,node,refs):
        ev=lambda n:self.evaluate(n,refs)
        if isinstance(node,ast.Constant):
            return node.value
        if isinstance(node,ast.BinOp):
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
            return ops[type(node.op)](ev(node.left),ev(node.right))
        if isinstance(node,ast.UnaryOp):
            return -ev(node.operand) if isinstance(node.op,ast.USub) else ev(node.operand)
        if isinstance(node,ast.Compare):
            ops={ast.Gt:operator.gt,ast.GtE:operator.ge,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Eq:operator.eq}
            return ops[type(node.ops[0])](ev(node.left),ev(node.comparators[0]))
        if isinstance(node,ast.Call):
            name=node.func.id
            if name=="REF":
                return self.cell(*refs[ev(node.args[0])])
            if name=="IF":
                return ev(node.args[1]) if ev(node.args[0]) else ev(node.args[2])
            if name=="AND":
                return all(ev(arg) for arg in node.args)
            values=[ev(arg) for arg in node.args]
            return {"MIN":lambda:min(values),"MAX":lambda:max(values),"ABS":lambda:abs(values[0]),
                    "ISNUMBER":lambda:isinstance(values[0],(int,float))}[name]()
        raise AssertionError(f"Unsupported formula syntax: {ast.dump(node)}")

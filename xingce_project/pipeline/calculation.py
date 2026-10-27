"""Small arithmetic verifier: no calls/attributes/names/exec or model code."""
import ast
from fractions import Fraction
OPS={ast.Add:lambda a,b:a+b,ast.Sub:lambda a,b:a-b,ast.Mult:lambda a,b:a*b,ast.Div:lambda a,b:a/b}
def evaluate(expression):
 if len(expression)>2000:raise ValueError('expression too long')
 tree=ast.parse(expression,mode='eval')
 def visit(n,depth=0):
  if depth>40:raise ValueError('expression too deep')
  if isinstance(n,ast.Constant) and type(n.value) in (int,float):
   token=ast.get_source_segment(expression,n);return Fraction(token)
  if isinstance(n,ast.BinOp) and type(n.op) in OPS:return OPS[type(n.op)](visit(n.left,depth+1),visit(n.right,depth+1))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return visit(n.operand,depth+1)*(1 if isinstance(n.op,ast.UAdd) else -1)
  raise ValueError('unsupported arithmetic node')
 return visit(tree.body)

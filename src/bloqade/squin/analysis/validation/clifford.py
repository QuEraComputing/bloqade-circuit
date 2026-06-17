import math
from kirin.validation import ValidationPass

class CliffordValidation(ValidationPass):
    
    #Validates that a SQuIN kernel only contains Clifford gates.
    #Accepts standard Cliffords and quarter-turn parameterized gates.
    #Rejects T gates, symbolic rotations, and non-quarter-turn rotations.
    

    def generic_visit(self, node):
        cls_name = node.__class__.__name__

        # 1. Reject explicitly non-Clifford gates
        if cls_name in ('T', 'TAdj', 'T_adj'):
            self.error(node, f"{cls_name} gate is not a Clifford gate.")
            
        # 2. Check parameterized gates for exact quarter-turns
        elif cls_name in ('RX', 'RY', 'RZ', 'PhasedXZ', 'U3'):
            self._check_node_params(node, cls_name)

        # Continue traversing the AST
        super().generic_visit(node)

    def _check_node_params(self, node, cls_name):
        # Known angular parameter names in SQuIN gate IR nodes
        angle_fields = ['theta', 'phi', 'lam', 'phase', 'angle']
        
        for field in angle_fields:
            if hasattr(node, field):
                p = getattr(node, field)
                if not self._is_quarter_turn(p):
                    self.error(node, f"{cls_name} gate contains a non-quarter-turn or symbolic rotation.")
                    return  

    def _is_quarter_turn(self, p):
        # Extract the defining operation if p is an SSA value from Kirin IR
        op = p
        if hasattr(p, 'owner'):
            op = p.owner
        elif hasattr(p, 'get_defining_op'):
            op = p.get_defining_op()

        # Extract the constant value
        val = None
        if hasattr(op, 'value'):
            val = op.value
        elif hasattr(op, 'data'):
            val = op.data

        # Unpack nested data wrappers if present
        if hasattr(val, 'data'):
            val = val.data
        if hasattr(val, 'value'):
            val = val.value

        if val is None:
            return False  
        if isinstance(val, (int, float)):
            if val == 0 or val == 0.0:
                return True
            quotient = val / (math.pi / 2)
            return math.isclose(quotient, round(quotient), abs_tol=1e-5)

        return False
from kirin.validation import ValidationPass
from bloqade.squin import stmts, expr

class CirqClassicalControlValidation(ValidationPass):
    """Validates that a SQuIN IfStmt can be emitted as a Cirq classical control."""
    
    def visit_IfStmt(self, node: stmts.IfStmt):
        # Criteria 1: Must be a direct boolean comparison against 1/0/True/False
        valid_condition = False
        if hasattr(node, 'condition') and hasattr(node.condition, 'op'):
            lhs = getattr(node.condition, 'lhs', None)
            rhs = getattr(node.condition, 'rhs', None)
            
            def is_valid_literal(n):
                return isinstance(n, expr.Constant) and n.value in (0, 1, True, False)
                
            def is_valid_measure_ref(n):
                return isinstance(n, expr.Var)
            
            if (is_valid_measure_ref(lhs) and is_valid_literal(rhs)) or \
               (is_valid_measure_ref(rhs) and is_valid_literal(lhs)):
                valid_condition = True
                
        if not valid_condition:
            self.error(node, "If statement condition must be a direct equality comparison against a single measurement using True/False or 1/0.")
            
        # Criteria 2: The else body must be empty
        if hasattr(node, 'else_body') and node.else_body is not None:
            if hasattr(node.else_body, 'stmts') and len(node.else_body.stmts) > 0:
                self.error(node, "Cirq classical control requires the 'else' body to be empty.")
                
        # Criteria 3: The then body must contain exactly one gate operation
        body_stmts = node.body.stmts if hasattr(node.body, 'stmts') else node.body
        if len(body_stmts) != 1 or not isinstance(body_stmts[0], (stmts.GateStmt, stmts.ApplyGate)):
            self.error(node, "Cirq classical control requires the 'then' body to contain exactly one gate operation.")

        self.generic_visit(node)
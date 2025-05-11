
class ComplexityAnalyzer:
    """
    Basic analyzer to estimate the time and space complexity of a solution.
    This uses heuristic-based analysis of AST (Abstract Syntax Tree).
    """
    def __init__(self):
        # Import here to avoid requiring ast for basic CLI functionality
        import ast
        self.ast = ast

    def analyze_file(self, file_path):
        """Analyze a Python file for time and space complexity."""
        with open(file_path, 'r') as file:
            code = file.read()
        
        # Parse the code into an AST
        tree = self.ast.parse(code)
        
        # Find the Solution class and its methods
        solution_class = None
        for node in tree.body:
            if isinstance(node, self.ast.ClassDef) and node.name == 'Solution':
                solution_class = node
                break
        
        if not solution_class:
            return {"error": "No Solution class found"}
        
        results = {}
        
        # Analyze each method in the Solution class
        for node in solution_class.body:
            if isinstance(node, self.ast.FunctionDef) and node.name != '__init__':
                method_name = node.name
                time_complexity, space_complexity, data_structures, is_recursive = self._analyze_function(node)
                
                results[method_name] = {
                    "time_complexity": time_complexity,
                    "space_complexity": space_complexity,
                    "explanation": self._generate_explanation(node, time_complexity, space_complexity, data_structures, is_recursive)
                }
        
        return results
    
    def _analyze_function(self, func_node):
        """Analyze a function's time and space complexity."""
        # Count loops and their nesting level
        loop_info = self._analyze_loops(func_node)
        
        # Check if function is recursive
        is_recursive = self._is_recursive(func_node)
        
        # Check for common data structures
        data_structures = self._check_data_structures(func_node)
        
        # Determine time complexity
        time_complexity = self._determine_time_complexity(loop_info, is_recursive, data_structures)
        
        # Determine space complexity
        space_complexity = self._determine_space_complexity(loop_info, is_recursive, data_structures)
        
        return time_complexity, space_complexity, data_structures, is_recursive
    
    def _analyze_loops(self, func_node):
        """Count loops and their nesting levels."""
        result = {
            "loops": 0,
            "max_nesting": 0
        }
        
        def visit_node(node, depth=0):
            is_loop = isinstance(node, (self.ast.For, self.ast.While))
            
            if is_loop:
                result["loops"] += 1
                current_depth = depth + 1
                result["max_nesting"] = max(result["max_nesting"], current_depth)
                
            
            # Visit all child nodes
            for child in self.ast.iter_child_nodes(node):
                visit_node(child, depth + 1 if is_loop else depth)
        
        visit_node(func_node)
        return result
    
    def _is_recursive(self, func_node):
        """Check if a function calls itself (recursive)."""
        function_name = func_node.name
        
        for node in self.ast.walk(func_node):
            if isinstance(node, self.ast.Call) and hasattr(node.func, 'id') \
               and node.func.id == function_name:
                return True
        return False
    
    def _check_data_structures(self, func_node):
        """Check for common data structures used in the function."""
        result = {
            "dict_or_set": False,  # O(1) lookups
            "sorting": False,      # O(n log n)
            "list_or_array": False # Linear data structures
        }
        
        for node in self.ast.walk(func_node):
            # Check for dictionary/set usage
            if isinstance(node, self.ast.Dict) or \
               (isinstance(node, self.ast.Call) and hasattr(node.func, 'id') 
                and node.func.id in ['dict', 'set']):
                result["dict_or_set"] = True
            
            # Check for sorting
            if isinstance(node, self.ast.Call) and hasattr(node.func, 'id') and node.func.id == 'sorted':
                result["sorting"] = True
            elif isinstance(node, self.ast.Call) and hasattr(node.func, 'attr') and node.func.attr == 'sort':
                result["sorting"] = True
            
            # Check for lists/arrays
            if isinstance(node, self.ast.List) or \
               (isinstance(node, self.ast.Call) and hasattr(node.func, 'id') and node.func.id == 'list'):
                result["list_or_array"] = True
        
        return result
    
    def _determine_time_complexity(self, loop_info, is_recursive, data_structures):
        """Determine the time complexity based on code patterns."""
        # Start with the most significant factors
        
        # Check for nested loops (O(n^k) where k is nesting level)
        if loop_info["max_nesting"] >= 3:
            return f"O(n^{loop_info['max_nesting']})"
        elif loop_info["max_nesting"] == 2:
            return "O(n²)"
        
        # Check for recursive patterns (often exponential or factorial)
        if is_recursive:
            # This is a simplification; recursion complexity can be complex
            return "O(2^n)"  # Assuming binary recursion
        
        # Check for sorting (O(n log n))
        if data_structures["sorting"]:
            return "O(n log n)"
        
        # Single loops are O(n)
        if loop_info["loops"] > 0:
            return "O(n)"
        
        # If using dictionaries/sets with constant time operations and no loops
        if data_structures["dict_or_set"] and loop_info["loops"] == 0:
            return "O(1)"
        
        # Default: if nothing specific is found, assume constant time
        return "O(1)"
    
    def _determine_space_complexity(self, loop_info, is_recursive, data_structures):
        """Determine the space complexity based on code patterns."""
        # Check for recursive patterns (often O(n) for stack space)
        if is_recursive:
            return "O(n)"  # Stack space for recursive calls
        
        # If using data structures that grow with input
        if data_structures["dict_or_set"] or data_structures["list_or_array"]:
            # Nested structures might use more space
            if loop_info["max_nesting"] > 1:
                return f"O(n^{loop_info['max_nesting']})"
            return "O(n)"
        
        # Default: if nothing specific is found, assume constant space
        return "O(1)"
    
    def _generate_explanation(self, func_node, time_complexity, space_complexity, data_structures, is_recursive):
        """Generate a human-readable explanation of the complexity analysis."""
        explanation = []
        
        # Time complexity explanation
        if time_complexity == "O(1)":
            explanation.append("Time Complexity: O(1) - Constant time")
            explanation.append("  • The solution uses a fixed number of operations regardless of input size.")
        
        elif time_complexity == "O(n)":
            explanation.append("Time Complexity: O(n) - Linear time")
            explanation.append("  • The solution iterates through the input once.")
        
        elif time_complexity == "O(n²)":
            explanation.append("Time Complexity: O(n²) - Quadratic time")
            explanation.append("  • The solution likely uses nested loops or quadratic algorithms.")
        
        elif time_complexity == "O(n log n)":
            explanation.append("Time Complexity: O(n log n)")
            explanation.append("  • The solution likely uses sorting or a divide-and-conquer approach.")
        
        elif "O(n^" in time_complexity:
            power = time_complexity.split("^")[1].rstrip(")")
            explanation.append(f"Time Complexity: {time_complexity} - Polynomial time")
            explanation.append(f"  • The solution uses {power} nested loops or similar polynomial complexity.")
        
        elif time_complexity == "O(2^n)":
            explanation.append("Time Complexity: O(2^n) - Exponential time")
            explanation.append("  • The solution likely uses recursive calls that branch at each step.")
        
        # Space complexity explanation
        if space_complexity == "O(1)":
            explanation.append("\nSpace Complexity: O(1) - Constant space")
            explanation.append("  • The solution uses a fixed amount of extra space regardless of input size.")
        
        elif space_complexity == "O(n)":
            explanation.append("\nSpace Complexity: O(n) - Linear space")
            explanation.append("  • The solution's memory usage grows linearly with the input size.")
            
        elif "O(n^" in space_complexity:
            power = space_complexity.split("^")[1].rstrip(")")
            explanation.append(f"\nSpace Complexity: {space_complexity}")
            explanation.append(f"  • The solution's memory usage grows with the {power}th power of the input size.")
        
        # Add optimization advice
        if time_complexity in ["O(n²)", "O(n^3)", "O(2^n)"]:
            explanation.append("\nOptimization Potential:")
            if not data_structures["dict_or_set"]:
                explanation.append("  • Consider using hash maps (dictionaries) for O(1) lookups.")
            if time_complexity == "O(2^n)" and is_recursive: # is_recursive is now directly available
                explanation.append("  • Consider memoization to avoid redundant recursive calculations.")
        
        return "\n".join(explanation)


#!/usr/bin/env python3
"""
YamlForge Schema Validation Tool

This script validates YAML files against the YamlForge schema and optionally fixes 
common schema violations automatically.

Usage:
    python tools/validate_schema.py [files...] [options]
    
    files        : Specific YAML files to validate (default: all files in examples/)
    --fix        : Automatically fix common schema violations
    --check-docs : Also check documentation files for schema compliance
    --verbose    : Show detailed output for each file processed

Examples:
    python tools/validate_schema.py                           # Validate all files in examples/
    python tools/validate_schema.py myfile.yaml              # Validate specific file
    python tools/validate_schema.py *.yaml --verbose         # Validate multiple files with details
    python tools/validate_schema.py --check-docs             # Include documentation checking
    python tools/validate_schema.py myfile.yaml --fix        # Validate and auto-fix violations
"""

import os
import sys
import json
import yaml
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class YamlForgeSchemaValidator:
    def __init__(self, schema_path: str = "docs/yamlforge-schema.json"):
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.fixes_applied = []
        self.errors_found = []
        
    def _load_schema(self) -> Dict[str, Any]:
        """Load the YamlForge JSON schema"""
        try:
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Schema file not found: {self.schema_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in schema file: {e}")
            sys.exit(1)
    
    def find_yaml_files(self, directory: str = "examples") -> List[str]:
        """Find all YAML files recursively in the given directory"""
        yaml_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    yaml_files.append(os.path.join(root, file))
        return sorted(yaml_files)
    
    def find_documentation_files(self) -> List[str]:
        """Find documentation files that might contain YAML examples"""
        doc_files = []
        
        # Main documentation files
        doc_patterns = [
            "README.md",
            "docs/**/*.md",
            "examples/README.md",
            "demobuilder/README.md"
        ]
        
        for pattern in doc_patterns:
            if "**" in pattern:
                # Handle glob patterns
                base_dir = pattern.split("**")[0]
                if os.path.exists(base_dir):
                    for root, dirs, files in os.walk(base_dir):
                        for file in files:
                            if file.endswith('.md'):
                                doc_files.append(os.path.join(root, file))
            else:
                if os.path.exists(pattern):
                    doc_files.append(pattern)
        
        return sorted(set(doc_files))
    
    def load_yaml_file(self, file_path: str) -> Tuple[Optional[Dict], List[str], List[str]]:
        """Load and parse a YAML file, return content, file lines, and any errors"""
        errors = []
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
                file_lines = file_content.split('\n')
                
            content = yaml.safe_load(file_content)
            return content, file_lines, errors
        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
            return None, [], errors
        except Exception as e:
            errors.append(f"File reading error: {e}")
            return None, [], errors
    
    def _find_line_number(self, file_lines: List[str], search_text: str) -> int:
        """Find the line number where a specific text appears"""
        if not file_lines:
            return 0
        
        for line_num, line in enumerate(file_lines, 1):
            if search_text in line:
                return line_num
        return 0
    
    def _find_property_line(self, file_lines: List[str], property_name: str) -> int:
        """Find the line number where a YAML property is defined"""
        if not file_lines:
            return 0
        
        # Look for the property with various YAML syntax patterns
        patterns = [
            f"{property_name}:",
            f'"{property_name}":',
            f"'{property_name}':",
        ]
        
        for line_num, line in enumerate(file_lines, 1):
            for pattern in patterns:
                if pattern in line:
                    return line_num
        return 0

    def validate_yaml_structure(self, content: Dict, file_path: str, file_lines: List[str] = None) -> List[str]:
        """Validate YAML structure against YamlForge schema requirements"""
        violations = []
        
        def add_violation(message: str, property_name: str = None):
            """Add a violation with optional line number"""
            if file_lines and property_name:
                line_num = self._find_property_line(file_lines, property_name)
                if line_num > 0:
                    violations.append(f"Line {line_num}: {message}")
                else:
                    violations.append(message)
            else:
                violations.append(message)
        
        if not isinstance(content, dict):
            violations.append("Root must be a dictionary")
            return violations
        
        # Check for required yamlforge section
        if 'yamlforge' not in content:
            add_violation("Missing required 'yamlforge' section", "yamlforge")
            return violations
        
        yamlforge_section = content['yamlforge']
        if not isinstance(yamlforge_section, dict):
            add_violation("'yamlforge' section must be a dictionary", "yamlforge")
            return violations
        
        # Check for required cloud_workspace
        if 'cloud_workspace' not in yamlforge_section:
            add_violation("Missing required 'cloud_workspace' section", "cloud_workspace")
        
        # Check GUID format if present
        if 'guid' in content:
            guid = content['guid']
            if not isinstance(guid, str) or not re.match(r'^[a-z0-9]{5}$', guid):
                add_violation(f"Invalid GUID format: '{guid}' (must be 5 lowercase alphanumeric characters)", "guid")
        
        # Check for invalid top-level properties
        valid_top_level = {'guid', 'yamlforge'}
        invalid_props = set(content.keys()) - valid_top_level
        if invalid_props:
            for prop in invalid_props:
                add_violation(f"Invalid top-level property: '{prop}'", prop)
        
        # Validate instances structure
        if 'instances' in yamlforge_section:
            violations.extend(self._validate_instances(yamlforge_section['instances'], file_lines))
        
        # Validate OpenShift clusters structure
        if 'openshift_clusters' in yamlforge_section:
            violations.extend(self._validate_openshift_clusters(yamlforge_section['openshift_clusters'], file_lines))
        
        return violations
    
    def _validate_instances(self, instances: List[Dict], file_lines: List[str] = None) -> List[str]:
        """Validate instances section"""
        violations = []
        
        if not isinstance(instances, list):
            violations.append("'instances' must be a list")
            return violations
        
        for i, instance in enumerate(instances):
            if not isinstance(instance, dict):
                violations.append(f"Instance {i+1} must be a dictionary")
                continue
            
            # Check for deprecated 'size' property (should be 'flavor')
            if 'size' in instance:
                line_num = self._find_property_line(file_lines, 'size') if file_lines else 0
                if line_num > 0:
                    violations.append(f"Line {line_num}: Instance {i+1} 'size' property is deprecated, use 'flavor' instead")
                else:
                    violations.append(f"Instance {i+1}: 'size' property is deprecated, use 'flavor' instead")
            
            # Check version format for OpenShift versions
            if 'version' in instance and isinstance(instance['version'], (int, float)):
                line_num = self._find_property_line(file_lines, 'version') if file_lines else 0
                if line_num > 0:
                    violations.append(f"Line {line_num}: Instance {i+1} 'version' should be a string, not number")
                else:
                    violations.append(f"Instance {i+1}: 'version' should be a string, not number")
            
            # Check for proper region vs location usage
            if 'region' in instance and 'location' in instance:
                violations.append(f"Instance {i+1}: Cannot use both 'region' and 'location', choose one")
        
        return violations
    
    def _validate_openshift_clusters(self, clusters: List[Dict], file_lines: List[str] = None) -> List[str]:
        """Validate OpenShift clusters section"""
        violations = []
        
        if not isinstance(clusters, list):
            violations.append("'openshift_clusters' must be a list")
            return violations
        
        for i, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                violations.append(f"OpenShift cluster {i+1} must be a dictionary")
                continue
            
            # Check version format
            if 'version' in cluster:
                version = cluster['version']
                if isinstance(version, (int, float)):
                    line_num = self._find_property_line(file_lines, 'version') if file_lines else 0
                    if line_num > 0:
                        violations.append(f"Line {line_num}: OpenShift cluster {i+1} 'version' should be a string, not number")
                    else:
                        violations.append(f"OpenShift cluster {i+1}: 'version' should be a string, not number")
                elif isinstance(version, str):
                    # Validate version pattern (should support 4.x.x format)
                    if not re.match(r'^(4\.\d+(?:\.\d+)?|latest)$', version):
                        line_num = self._find_property_line(file_lines, 'version') if file_lines else 0
                        if line_num > 0:
                            violations.append(f"Line {line_num}: OpenShift cluster {i+1} invalid version format '{version}'")
                        else:
                            violations.append(f"OpenShift cluster {i+1}: Invalid version format '{version}'")
        
        return violations
    
    def fix_yaml_violations(self, content: Dict, violations: List[str], file_path: str) -> Tuple[Dict, List[str]]:
        """Automatically fix common schema violations"""
        fixes_applied = []
        
        # Fix deprecated 'size' to 'flavor' in instances
        if 'yamlforge' in content and 'instances' in content['yamlforge']:
            for i, instance in enumerate(content['yamlforge']['instances']):
                if 'size' in instance:
                    instance['flavor'] = instance.pop('size')
                    fixes_applied.append(f"Instance {i+1}: Changed 'size' to 'flavor'")
                
                # Fix numeric versions to strings
                if 'version' in instance and isinstance(instance['version'], (int, float)):
                    instance['version'] = str(instance['version'])
                    fixes_applied.append(f"Instance {i+1}: Converted version to string")
        
        # Fix numeric versions in OpenShift clusters
        if 'yamlforge' in content and 'openshift_clusters' in content['yamlforge']:
            for i, cluster in enumerate(content['yamlforge']['openshift_clusters']):
                if 'version' in cluster and isinstance(cluster['version'], (int, float)):
                    cluster['version'] = str(cluster['version'])
                    fixes_applied.append(f"OpenShift cluster {i+1}: Converted version to string")
        
        # Remove invalid top-level properties (except guid and yamlforge)
        valid_top_level = {'guid', 'yamlforge'}
        invalid_props = set(content.keys()) - valid_top_level
        for prop in invalid_props:
            content.pop(prop)
            fixes_applied.append(f"Removed invalid top-level property: '{prop}'")
        
        return content, fixes_applied
    
    def save_yaml_file(self, content: Dict, file_path: str) -> bool:
        """Save YAML content back to file"""
        try:
            with open(file_path, 'w') as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"ERROR: Failed to save {file_path}: {e}")
            return False
    
    def check_documentation_examples(self, doc_files: List[str]) -> List[Tuple[str, List[str]]]:
        """Check YAML examples in documentation files"""
        doc_violations = []
        
        for doc_file in doc_files:
            try:
                with open(doc_file, 'r') as f:
                    content = f.read()
                
                violations = []
                lines = content.split('\n')
                
                # Find YAML code blocks with line numbers
                yaml_pattern = re.compile(r'```yaml\n(.*?)\n```', re.DOTALL)
                
                for match in yaml_pattern.finditer(content):
                    yaml_block = match.group(1)
                    
                    # Check if this YAML block should be skipped for validation
                    # Educational examples can use: # yamlforge-validation: skip-schema-errors
                    if 'yamlforge-validation: skip-schema-errors' in yaml_block:
                        continue  # Skip validation for educational examples that intentionally show errors
                    
                    # Calculate line number where YAML block starts
                    start_pos = match.start()
                    line_num = content[:start_pos].count('\n') + 2  # +2 for ```yaml line
                    
                    try:
                        yaml_content = yaml.safe_load(yaml_block)
                        if isinstance(yaml_content, dict) and 'yamlforge' in yaml_content:
                            block_violations = self.validate_yaml_structure(yaml_content, f"{doc_file}:line_{line_num}")
                            if block_violations:
                                violations.extend([f"YAML block at line {line_num}: {v}" for v in block_violations])
                    except yaml.YAMLError as e:
                        violations.append(f"YAML block at line {line_num}: Invalid YAML - {e}")
                        continue
                
                # Check for deprecated patterns in documentation with line numbers
                deprecated_patterns = [
                    # Match "size:" but exclude legitimate field names like "worker_disk_size:", "disk_size:", etc.
                    # Use negative lookbehind to avoid matching words ending with "_size:"
                    (r'(?<![a-zA-Z_])size:\s*["\']?\w+["\']?', "Use 'flavor' instead of 'size'"),
                    (r'region:\s*["\']?us-east["\']?', "Use 'location: us-east' for universal mapping or specific cloud region"),
                ]
                
                for pattern, message in deprecated_patterns:
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            violations.append(f"Line {line_num}: Deprecated pattern - {message}")
                
                if violations:
                    doc_violations.append((doc_file, violations))
                    
            except Exception as e:
                doc_violations.append((doc_file, [f"Error reading file: {e}"]))
        
        return doc_violations
    
    def run_validation(self, fix_files: bool = False, check_docs: bool = False, verbose: bool = False, specific_files: List[str] = None) -> bool:
        """Run complete validation process"""
        print("YamlForge Schema Validation Tool")
        print("=" * 40)
        
        # Find YAML files
        if specific_files:
            # Validate specific files provided by user
            yaml_files = []
            for file_path in specific_files:
                if os.path.exists(file_path):
                    if file_path.endswith(('.yaml', '.yml')):
                        yaml_files.append(file_path)
                    else:
                        print(f"Warning: {file_path} is not a YAML file (skipping)")
                else:
                    print(f"Error: {file_path} does not exist")
                    return False
            print(f"Validating {len(yaml_files)} specified YAML files")
        else:
            # Find all YAML files in examples directory
            yaml_files = self.find_yaml_files()
            print(f"Found {len(yaml_files)} YAML files to validate")
        
        success = True
        total_violations = 0
        total_fixes = 0
        
        # Validate YAML files
        for file_path in yaml_files:
            if verbose:
                print(f"\nProcessing: {file_path}")
            
            content, file_lines, load_errors = self.load_yaml_file(file_path)
            
            if load_errors:
                print(f"❌ {file_path}: {', '.join(load_errors)}")
                success = False
                continue
            
            if content is None:
                continue
            
            violations = self.validate_yaml_structure(content, file_path, file_lines)
            
            if violations:
                total_violations += len(violations)
                
                if fix_files:
                    # Attempt to fix violations
                    fixed_content, fixes = self.fix_yaml_violations(content, violations, file_path)
                    
                    if fixes:
                        if self.save_yaml_file(fixed_content, file_path):
                            print(f"🔧 {file_path}: Fixed {len(fixes)} issues")
                            if verbose:
                                for fix in fixes:
                                    print(f"   - {fix}")
                            total_fixes += len(fixes)
                        else:
                            print(f"❌ {file_path}: Failed to save fixes")
                            success = False
                    
                    # Re-validate after fixes
                    remaining_violations = self.validate_yaml_structure(fixed_content, file_path, file_lines)
                    if remaining_violations:
                        print(f"⚠️  {file_path}: {len(remaining_violations)} issues remain")
                        if verbose:
                            for violation in remaining_violations:
                                print(f"   - {violation}")
                        success = False
                    else:
                        print(f"✅ {file_path}: All issues resolved")
                else:
                    print(f"❌ {file_path}: {len(violations)} violations")
                    if verbose:
                        for violation in violations:
                            print(f"   - {violation}")
                    success = False
            else:
                if verbose:
                    print(f"✅ {file_path}: Valid")
        
        # Check documentation files if requested
        if check_docs:
            print(f"\nChecking documentation files...")
            doc_files = self.find_documentation_files()
            doc_violations = self.check_documentation_examples(doc_files)
            
            if doc_violations:
                print(f"\nDocumentation Issues Found:")
                for doc_file, violations in doc_violations:
                    print(f"❌ {doc_file}:")
                    for violation in violations:
                        print(f"   - {violation}")
                success = False
            else:
                print("✅ All documentation examples are valid")
        
        # Summary
        print(f"\nValidation Summary:")
        print(f"Files processed: {len(yaml_files)}")
        print(f"Total violations found: {total_violations}")
        if fix_files:
            print(f"Total fixes applied: {total_fixes}")
        
        if success:
            print("🎉 All files are schema-compliant!")
        else:
            print("❌ Schema violations found. Use --fix to automatically resolve common issues.")
        
        return success

def main():
    parser = argparse.ArgumentParser(description="Validate YamlForge YAML files against schema")
    parser.add_argument("files", nargs="*", help="Specific YAML files to validate (default: all files in examples/)")
    parser.add_argument("--fix", action="store_true", help="Automatically fix common schema violations")
    parser.add_argument("--check-docs", action="store_true", help="Also check documentation files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    args = parser.parse_args()
    
    validator = YamlForgeSchemaValidator()
    success = validator.run_validation(
        fix_files=args.fix,
        check_docs=args.check_docs,
        verbose=args.verbose,
        specific_files=args.files if args.files else None
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
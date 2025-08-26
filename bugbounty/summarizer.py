"""
Analysis and summarization module for bug bounty results.
Implements heuristic analysis, result filtering, and report generation.
"""

import re
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import glob
from jsonpath_ng import parse as jsonpath_parse

from .config import config
from .utils import read_json, write_json, create_zip_archive, safe_filename, get_file_size_mb


class JuicyFilter:
    """Represents a single juicy filter rule."""
    
    def __init__(self, rule_config: Dict[str, Any]):
        self.id = rule_config['id']
        self.description = rule_config.get('desc', rule_config.get('description', ''))
        self.file_globs = rule_config.get('file_globs', [])
        self.regex_patterns = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) 
                              for pattern in rule_config.get('regex', [])]
        self.json_paths = rule_config.get('json_path', [])
        self.min_matches = rule_config.get('min_matches', 1)
        self.max_matches = rule_config.get('max_matches', 100)
        self.exclude_patterns = [re.compile(pattern, re.IGNORECASE) 
                               for pattern in rule_config.get('exclude', [])]
    
    def matches_file(self, file_path: Path) -> bool:
        """Check if file matches the filter's file patterns."""
        if not self.file_globs:
            return True
        
        for pattern in self.file_globs:
            if file_path.match(pattern):
                return True
        return False


class Finding:
    """Represents a single finding from analysis."""
    
    def __init__(self, rule_id: str, rule_desc: str, file_path: Path, 
                 line_number: int = None, match_text: str = None, 
                 context: str = None, metadata: Dict[str, Any] = None):
        self.rule_id = rule_id
        self.rule_description = rule_desc
        self.file_path = file_path
        self.line_number = line_number
        self.match_text = match_text
        self.context = context
        self.metadata = metadata or {}
        self.confidence = metadata.get('confidence', 'medium')
        self.severity = metadata.get('severity', 'info')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary."""
        return {
            'rule_id': self.rule_id,
            'rule_description': self.rule_description,
            'file_path': str(self.file_path),
            'line_number': self.line_number,
            'match_text': self.match_text,
            'context': self.context,
            'confidence': self.confidence,
            'severity': self.severity,
            'metadata': self.metadata
        }


class Summarizer:
    """Main summarizer class for analyzing bug bounty results."""
    
    def __init__(self, target: str):
        self.target = target
        self.target_dir = config.target_dir(target)
        self.outputs_dir = config.outputs_dir(target)
        self.reports_dir = config.reports_dir(target)
        self.filters = []
        self.findings = []
        
        # Load filters
        self._load_filters()
    
    def _load_filters(self):
        """Load juicy filters from configuration."""
        filters_file = config.ROOT_DIR / "templates" / "juicy_filters.yaml"
        
        if not filters_file.exists():
            # Create default filters if none exist
            self._create_default_filters()
        
        try:
            with open(filters_file, 'r', encoding='utf-8') as f:
                filters_config = yaml.safe_load(f)
            
            self.filters = []
            for rule_config in filters_config.get('rules', []):
                try:
                    filter_obj = JuicyFilter(rule_config)
                    self.filters.append(filter_obj)
                except Exception as e:
                    print(f"Error loading filter {rule_config.get('id', 'unknown')}: {e}")
        
        except Exception as e:
            print(f"Error loading filters: {e}")
            self.filters = []
    
    def _create_default_filters(self):
        """Create default juicy filters."""
        default_filters = {
            'rules': [
                {
                    'id': 'secrets',
                    'desc': 'Possible secrets and API keys',
                    'file_globs': ['**/*.js', '**/*.txt', '**/*.log', '**/*.json', '**/*.xml'],
                    'regex': [
                        r'AKIA[0-9A-Z]{16}',  # AWS Access Key
                        r'(?i)(secret|api[-_]?key|token|password)[\s:="\'\[]{0,5}([A-Za-z0-9_\-]{16,})',
                        r'(?i)(bearer|authorization)[\s:="\'\[]{0,5}([A-Za-z0-9_\-\.]{20,})',
                        r'(?i)-----BEGIN [A-Z ]+-----',  # Private keys
                        r'sk_live_[0-9a-zA-Z]{24}',  # Stripe keys
                        r'pk_live_[0-9a-zA-Z]{24}',  # Stripe keys
                        r'ghp_[A-Za-z0-9]{36}',  # GitHub personal access tokens
                        r'gho_[A-Za-z0-9]{36}',  # GitHub OAuth tokens
                    ]
                },
                {
                    'id': 'endpoints_with_params',
                    'desc': 'Endpoints with parameters',
                    'file_globs': ['**/endpoints/**/*.txt', '**/web/**/*.json'],
                    'regex': [
                        r'https?://[^\s]+\?[a-zA-Z0-9_]+=',
                        r'[\'"`]\/[^\'"`\s]*\?[a-zA-Z0-9_]+=',
                    ]
                },
                {
                    'id': 'interesting_status_codes',
                    'desc': 'Interesting HTTP status codes',
                    'file_globs': ['**/web/**/*.json', '**/web/**/*.txt'],
                    'regex': [
                        r'"status_code":\s*(403|500|502|503)',
                        r'\[403\]|\[500\]|\[502\]|\[503\]',
                    ]
                },
                {
                    'id': 'admin_panels',
                    'desc': 'Potential admin panels',
                    'file_globs': ['**/*.txt', '**/*.json'],
                    'regex': [
                        r'(?i)\/admin[\/\s]',
                        r'(?i)\/administrator[\/\s]',
                        r'(?i)\/wp-admin[\/\s]',
                        r'(?i)\/cpanel[\/\s]',
                        r'(?i)\/manager[\/\s]',
                        r'(?i)\/dashboard[\/\s]',
                    ]
                },
                {
                    'id': 'sensitive_files',
                    'desc': 'Sensitive files and backups',
                    'file_globs': ['**/*.txt', '**/*.json'],
                    'regex': [
                        r'\.git/config',
                        r'\.env\.?[a-zA-Z]*',
                        r'config\.php',
                        r'\.backup',
                        r'\.sql',
                        r'\.db',
                        r'robots\.txt',
                        r'sitemap\.xml',
                    ]
                },
                {
                    'id': 'technology_indicators',
                    'desc': 'Technology and framework indicators',
                    'file_globs': ['**/web/**/*.json', '**/*.txt'],
                    'regex': [
                        r'"server":\s*"([^"]+)"',
                        r'"technology":\s*"([^"]+)"',
                        r'X-Powered-By:\s*([^\r\n]+)',
                        r'(?i)(php|asp|jsp|python|node\.js|django|flask|laravel)',
                    ]
                }
            ]
        }
        
        filters_file = config.ROOT_DIR / "templates" / "juicy_filters.yaml"
        filters_file.parent.mkdir(exist_ok=True)
        
        with open(filters_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_filters, f, default_flow_style=False, indent=2)
    
    def analyze(self) -> List[Finding]:
        """
        Analyze all output files using loaded filters.
        
        Returns:
            List of findings
        """
        self.findings = []
        
        if not self.outputs_dir.exists():
            return self.findings
        
        # Get all files in outputs directory
        all_files = list(self.outputs_dir.rglob('*'))
        text_files = [f for f in all_files if f.is_file() and self._is_text_file(f)]
        
        for filter_obj in self.filters:
            # Find matching files for this filter
            matching_files = [f for f in text_files if filter_obj.matches_file(f)]
            
            for file_path in matching_files:
                try:
                    findings = self._analyze_file(file_path, filter_obj)
                    self.findings.extend(findings)
                except Exception as e:
                    print(f"Error analyzing {file_path} with filter {filter_obj.id}: {e}")
        
        # Sort findings by confidence and severity
        self.findings.sort(key=lambda f: (f.confidence, f.severity), reverse=True)
        
        return self.findings
    
    def _analyze_file(self, file_path: Path, filter_obj: JuicyFilter) -> List[Finding]:
        """Analyze a single file with a specific filter."""
        findings = []
        
        try:
            # Read file content
            if file_path.suffix.lower() == '.json':
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                findings.extend(self._analyze_json_file(file_path, filter_obj, content))
            else:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                findings.extend(self._analyze_text_file(file_path, filter_obj, content))
        
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
        
        return findings
    
    def _analyze_text_file(self, file_path: Path, filter_obj: JuicyFilter, content: str) -> List[Finding]:
        """Analyze text file content."""
        findings = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in filter_obj.regex_patterns:
                matches = pattern.finditer(line)
                
                for match in matches:
                    # Check exclude patterns
                    if any(excl.search(match.group(0)) for excl in filter_obj.exclude_patterns):
                        continue
                    
                    # Create context (line before and after)
                    context_lines = []
                    for i in range(max(0, line_num - 2), min(len(lines), line_num + 1)):
                        context_lines.append(f"{i+1:4d}: {lines[i]}")
                    context = '\n'.join(context_lines)
                    
                    finding = Finding(
                        rule_id=filter_obj.id,
                        rule_desc=filter_obj.description,
                        file_path=file_path.relative_to(self.target_dir),
                        line_number=line_num,
                        match_text=match.group(0),
                        context=context,
                        metadata={
                            'confidence': self._calculate_confidence(match.group(0), filter_obj.id),
                            'severity': self._calculate_severity(filter_obj.id),
                            'pattern': pattern.pattern
                        }
                    )
                    findings.append(finding)
        
        return findings[:filter_obj.max_matches]
    
    def _analyze_json_file(self, file_path: Path, filter_obj: JuicyFilter, content: str) -> List[Finding]:
        """Analyze JSON file content."""
        findings = []
        
        try:
            json_data = json.loads(content)
            
            # Apply regex patterns to JSON content as text
            text_findings = self._analyze_text_file(file_path, filter_obj, content)
            findings.extend(text_findings)
            
            # Apply JSONPath queries if specified
            for json_path in filter_obj.json_paths:
                try:
                    jsonpath_expr = jsonpath_parse(json_path)
                    matches = jsonpath_expr.find(json_data)
                    
                    for match in matches:
                        finding = Finding(
                            rule_id=filter_obj.id,
                            rule_desc=filter_obj.description,
                            file_path=file_path.relative_to(self.target_dir),
                            match_text=str(match.value),
                            context=f"JSONPath: {json_path}",
                            metadata={
                                'confidence': 'high',
                                'severity': self._calculate_severity(filter_obj.id),
                                'json_path': json_path,
                                'json_value': match.value
                            }
                        )
                        findings.append(finding)
                
                except Exception as e:
                    print(f"Error applying JSONPath {json_path}: {e}")
        
        except json.JSONDecodeError:
            # If not valid JSON, fall back to text analysis
            pass
        
        return findings
    
    def _calculate_confidence(self, match_text: str, rule_id: str) -> str:
        """Calculate confidence level for a match."""
        if rule_id == 'secrets':
            if len(match_text) > 30:
                return 'high'
            elif len(match_text) > 20:
                return 'medium'
            else:
                return 'low'
        elif rule_id in ['admin_panels', 'sensitive_files']:
            return 'high'
        else:
            return 'medium'
    
    def _calculate_severity(self, rule_id: str) -> str:
        """Calculate severity level for a rule."""
        high_severity_rules = ['secrets', 'admin_panels', 'sensitive_files']
        medium_severity_rules = ['endpoints_with_params', 'interesting_status_codes']
        
        if rule_id in high_severity_rules:
            return 'high'
        elif rule_id in medium_severity_rules:
            return 'medium'
        else:
            return 'low'
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file."""
        text_extensions = {'.txt', '.log', '.json', '.xml', '.html', '.js', '.css', '.md', '.yml', '.yaml'}
        
        if file_path.suffix.lower() in text_extensions:
            return True
        
        # Check if file has no extension but might be text
        if not file_path.suffix:
            try:
                file_path.read_text(encoding='utf-8', errors='strict')
                return True
            except (UnicodeDecodeError, IOError):
                return False
        
        return False
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate complete summary with analysis and reports.
        
        Returns:
            Summary dictionary
        """
        # Ensure reports directory exists
        self.reports_dir.mkdir(exist_ok=True)
        
        # Run analysis
        findings = self.analyze()
        
        # Generate statistics
        stats = self._generate_statistics()
        
        # Create summary data
        summary_data = {
            'target': self.target,
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'findings': [f.to_dict() for f in findings],
            'top_findings': self._get_top_findings(findings, 20),
            'files_analyzed': self._get_analyzed_files_info()
        }
        
        # Write JSON summary
        summary_json_path = self.reports_dir / "summary.json"
        write_json(summary_json_path, summary_data)
        
        # Write Markdown summary
        summary_md_path = self.reports_dir / "summary.md"
        markdown_content = self._generate_markdown_summary(summary_data)
        summary_md_path.write_text(markdown_content, encoding='utf-8')
        
        # Create ZIP archive
        self._create_results_zip()
        
        return summary_data
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not self.outputs_dir.exists():
            return {}
        
        # Count files by type
        all_files = list(self.outputs_dir.rglob('*'))
        file_count = len([f for f in all_files if f.is_file()])
        
        # Count findings by rule
        findings_by_rule = {}
        for finding in self.findings:
            rule_id = finding.rule_id
            findings_by_rule[rule_id] = findings_by_rule.get(rule_id, 0) + 1
        
        # Count by severity
        findings_by_severity = {'high': 0, 'medium': 0, 'low': 0}
        for finding in self.findings:
            severity = finding.severity
            findings_by_severity[severity] = findings_by_severity.get(severity, 0) + 1
        
        return {
            'total_files': file_count,
            'total_findings': len(self.findings),
            'findings_by_rule': findings_by_rule,
            'findings_by_severity': findings_by_severity,
            'high_confidence_findings': len([f for f in self.findings if f.confidence == 'high']),
        }
    
    def _get_top_findings(self, findings: List[Finding], limit: int = 20) -> List[Dict[str, Any]]:
        """Get top findings by priority."""
        # Sort by severity and confidence
        priority_map = {
            ('high', 'high'): 1,
            ('high', 'medium'): 2,
            ('medium', 'high'): 3,
            ('high', 'low'): 4,
            ('medium', 'medium'): 5,
            ('low', 'high'): 6,
            ('medium', 'low'): 7,
            ('low', 'medium'): 8,
            ('low', 'low'): 9
        }
        
        sorted_findings = sorted(
            findings,
            key=lambda f: priority_map.get((f.severity, f.confidence), 10)
        )
        
        return [f.to_dict() for f in sorted_findings[:limit]]
    
    def _get_analyzed_files_info(self) -> List[Dict[str, Any]]:
        """Get information about analyzed files."""
        if not self.outputs_dir.exists():
            return []
        
        files_info = []
        all_files = list(self.outputs_dir.rglob('*'))
        
        for file_path in all_files:
            if file_path.is_file():
                files_info.append({
                    'path': str(file_path.relative_to(self.target_dir)),
                    'size_mb': get_file_size_mb(file_path),
                    'type': file_path.suffix or 'no_extension'
                })
        
        return sorted(files_info, key=lambda x: x['size_mb'], reverse=True)
    
    def _generate_markdown_summary(self, summary_data: Dict[str, Any]) -> str:
        """Generate Markdown summary report."""
        md_lines = [
            f"# Bug Bounty Summary Report",
            f"",
            f"**Target:** {summary_data['target']}  ",
            f"**Generated:** {summary_data['generated_at']}  ",
            f"",
            f"## 📊 Statistics",
            f"",
        ]
        
        stats = summary_data['statistics']
        if stats:
            md_lines.extend([
                f"- **Total Files:** {stats.get('total_files', 0)}",
                f"- **Total Findings:** {stats.get('total_findings', 0)}",
                f"- **High Confidence:** {stats.get('high_confidence_findings', 0)}",
                f"",
                f"### Findings by Severity",
                f"",
            ])
            
            for severity, count in stats.get('findings_by_severity', {}).items():
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                md_lines.append(f"- {emoji} **{severity.title()}:** {count}")
            
            md_lines.extend([
                f"",
                f"### Findings by Rule",
                f"",
            ])
            
            for rule, count in stats.get('findings_by_rule', {}).items():
                md_lines.append(f"- **{rule}:** {count}")
        
        # Top findings
        top_findings = summary_data.get('top_findings', [])
        if top_findings:
            md_lines.extend([
                f"",
                f"## 🎯 Top Findings",
                f"",
            ])
            
            for i, finding in enumerate(top_findings[:10], 1):
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(finding['severity'], "⚪")
                confidence_emoji = {"high": "💯", "medium": "🎯", "low": "🤔"}.get(finding['confidence'], "❓")
                
                md_lines.extend([
                    f"### {i}. {finding['rule_description']} {severity_emoji} {confidence_emoji}",
                    f"",
                    f"**File:** `{finding['file_path']}`  ",
                ])
                
                if finding['line_number']:
                    md_lines.append(f"**Line:** {finding['line_number']}  ")
                
                if finding['match_text']:
                    md_lines.extend([
                        f"**Match:**",
                        f"```",
                        finding['match_text'][:200] + ("..." if len(finding['match_text']) > 200 else ""),
                        f"```",
                    ])
                
                md_lines.append("")
        
        return '\n'.join(md_lines)
    
    def _create_results_zip(self):
        """Create ZIP archive with results."""
        zip_path = self.reports_dir / "results.zip"
        
        # Include important files
        include_patterns = [
            "reports/**",
            "outputs/**/subfinder*.txt",
            "outputs/**/httpx*.json",
            "outputs/**/katana*.txt",
            "logs/runner.log"
        ]
        
        exclude_patterns = [
            "*.tmp",
            "*.lock",
            "__pycache__/**"
        ]
        
        try:
            create_zip_archive(self.target_dir, zip_path, exclude_patterns)
            return zip_path
        except Exception as e:
            print(f"Error creating ZIP archive: {e}")
            return None
#!/usr/bin/env python3
"""
R0TBB Security Report Generator
Generates detailed security reports from scan results
"""

import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path
import argparse

class SecurityReportGenerator:
    def __init__(self, target_dir):
        self.target_dir = Path(target_dir)
        self.findings = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'info': []
        }
        
    def analyze_nuclei_results(self):
        """Analyze nuclei scan results and categorize findings"""
        nuclei_file = self.target_dir / "outputs" / "scans" / "nuclei_tokens.json"
        if not nuclei_file.exists():
            return
            
        try:
            with open(nuclei_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return
                    
            # Parse nuclei results using regex
            lines = content.split('\n')
            for line in lines:
                if '[' in line and ']' in line:
                    # Use regex to extract components
                    # Format: [finding-type] [http] [severity] URL [details]
                    import re
                    
                    # Extract finding type
                    finding_match = re.match(r'\[([^\]]+)\]', line)
                    if finding_match:
                        finding_type = finding_match.group(1)
                        
                        # Extract severity (third bracket)
                        severity_match = re.search(r'\] \[([^\]]+)\] \[([^\]]+)\]', line)
                        if severity_match:
                            severity = severity_match.group(2)
                            
                            # Extract URL (after third bracket)
                            url_match = re.search(r'\] \[([^\]]+)\] \[([^\]]+)\] (https?://[^\s\[]+)', line)
                            if url_match:
                                url = url_match.group(3)
                                
                                # Extract details (everything after URL)
                                details_start = line.find(url) + len(url)
                                details = line[details_start:].strip()
                                
                                # Clean up details
                                if details.startswith('['):
                                    details = details[1:]
                                if details.endswith(']'):
                                    details = details[:-1]
                            
                            # Categorize by severity and finding type
                            categorized_severity = self.categorize_finding_severity(finding_type, severity, details)
                            self.findings[categorized_severity].append({
                                'type': finding_type,
                                'url': url,
                                'details': details,
                                'severity': severity
                            })
        except Exception as e:
            print(f"Error parsing nuclei results: {e}")
    
    def categorize_finding_severity(self, finding_type, severity, details):
        """Categorize findings by severity based on type and content"""
        finding_type_lower = finding_type.lower()
        
        # Credentials disclosure is typically HIGH severity
        if 'credentials-disclosure' in finding_type_lower:
            return 'high'
        
        # API key exposures are HIGH severity
        if 'api-key' in finding_type_lower or 'google-api-key' in finding_type_lower:
            return 'high'
        
        # Exposed file upload forms are MEDIUM severity
        if 'exposed-file-upload-form' in finding_type_lower:
            return 'medium'
        
        # Default categorization based on nuclei severity
        if 'critical' in severity.lower():
            return 'critical'
        elif 'high' in severity.lower():
            return 'high'
        elif 'medium' in severity.lower():
            return 'medium'
        elif 'low' in severity.lower():
            return 'low'
        elif 'unknown' in severity.lower():
            # Unknown severity findings get categorized by type
            if 'credentials' in finding_type_lower or 'api' in finding_type_lower:
                return 'high'
            elif 'upload' in finding_type_lower or 'form' in finding_type_lower:
                return 'medium'
            else:
                return 'info'
        else:
            return 'info'
    
    def extract_api_keys(self):
        """Extract API keys from findings and categorize by severity"""
        api_keys = []
        for severity in self.findings.values():
            for finding in severity:
                if 'api' in finding['type'].lower() or 'key' in finding['type'].lower():
                    # Extract API keys using regex
                    keys = re.findall(r'AIza[a-zA-Z0-9_-]{35}', finding['details'])
                    for key in keys:
                        # Categorize API key severity
                        key_severity = self.categorize_api_key_severity(key, finding['url'], finding['type'])
                        api_keys.append({
                            'key': key,
                            'url': finding['url'],
                            'type': finding['type'],
                            'severity': key_severity,
                            'description': self.get_api_key_description(key, finding['url'])
                        })
        return api_keys
    
    def categorize_api_key_severity(self, key, url, finding_type):
        """Categorize API key exposure by severity"""
        # Google API keys in frontend JS files are typically HIGH severity
        if 'google' in finding_type.lower() or 'firebase' in url.lower():
            return 'HIGH'
        # API keys in production environments are more critical
        elif 'production' in url.lower() or 'prod' in url.lower():
            return 'HIGH'
        # API keys in development/test environments are medium
        elif 'dev' in url.lower() or 'test' in url.lower() or 'staging' in url.lower():
            return 'MEDIUM'
        # Default to medium for unknown contexts
        else:
            return 'MEDIUM'
    
    def get_api_key_description(self, key, url):
        """Get description of the API key exposure"""
        if 'firebase' in url.lower():
            return "Firebase API Key exposed in frontend JavaScript - Can be used to access Firebase services"
        elif 'google' in url.lower():
            return "Google API Key exposed in frontend JavaScript - Can be used to access Google services"
        else:
            return "API Key exposed in frontend JavaScript - Potential security risk"
    
    def analyze_tech_stack(self):
        """Analyze technology stack findings"""
        tech_file = self.target_dir / "outputs" / "web" / "tech_stack.txt"
        if not tech_file.exists():
            return {}
            
        tech_stack = {}
        try:
            with open(tech_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Extract URL
                    url_match = re.search(r'(https?://[^\s]+)', line)
                    if not url_match:
                        continue
                        
                    url = url_match.group(1)
                    
                    # Extract all bracketed content
                    brackets = re.findall(r'\[([^\]]+)\]', line)
                    
                    # Extract status code and technologies
                    status_code = None
                    technologies = []
                    
                    for bracket in brackets:
                        bracket = bracket.strip()
                        
                        # Clean ANSI codes first
                        cleaned_bracket = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', bracket)
                        cleaned_bracket = re.sub(r'\[\d+m', '', cleaned_bracket)
                        cleaned_bracket = cleaned_bracket.strip()
                        
                        # Check if it's a status code (200, 301, 403, etc.)
                        if re.match(r'^\d{3}$', cleaned_bracket) or re.match(r'^\d{2}$', cleaned_bracket):
                            status_code = cleaned_bracket
                            continue
                            
                        # Skip if it's just a single digit
                        if re.match(r'^\d$', cleaned_bracket):
                            continue
                            
                        # Skip if it's a page title (contains spaces, dashes, or is too long)
                        if ' ' in cleaned_bracket or '-' in cleaned_bracket or len(cleaned_bracket) > 30:
                            continue
                            
                        # Skip common non-technology strings
                        if cleaned_bracket.lower() in ['forbidden', 'not found', 'welcome to nginx']:
                            continue
                            
                        if cleaned_bracket and len(cleaned_bracket) > 1:
                            # Final check: skip if it's just a status code
                            if not re.match(r'^\d+$', cleaned_bracket):
                                technologies.append(cleaned_bracket)
                    
                    if technologies or status_code:
                        tech_stack[url] = {
                            'status_code': status_code,
                            'technologies': technologies
                        }
                        
        except Exception as e:
            print(f"Error parsing tech stack: {e}")
            
        return tech_stack
    
    def get_subdomain_stats(self):
        """Get subdomain enumeration statistics"""
        subdomains_file = self.target_dir / "outputs" / "recon" / "alive_subdomains.txt"
        if not subdomains_file.exists():
            return 0
            
        try:
            with open(subdomains_file, 'r') as f:
                return len(f.readlines())
        except:
            return 0
    
    def get_js_files_count(self):
        """Get JavaScript files count"""
        js_file = self.target_dir / "outputs" / "endpoints" / "alive_jsfile.txt"
        if not js_file.exists():
            return 0
            
        try:
            with open(js_file, 'r') as f:
                return len(f.readlines())
        except:
            return 0
    
    def generate_report(self, output_format='text'):
        """Generate the security report"""
        self.analyze_nuclei_results()
        api_keys = self.extract_api_keys()
        tech_stack = self.analyze_tech_stack()
        
        # Count API keys by severity
        high_api_keys = len([k for k in api_keys if k['severity'] == 'HIGH'])
        medium_api_keys = len([k for k in api_keys if k['severity'] == 'MEDIUM'])
        low_api_keys = len([k for k in api_keys if k['severity'] == 'LOW'])
        
        report = {
            'target': self.target_dir.name,
            'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'statistics': {
                'subdomains_found': self.get_subdomain_stats(),
                'js_files_found': self.get_js_files_count(),
                'total_findings': sum(len(findings) for findings in self.findings.values()) + len(api_keys),
                'critical_findings': len(self.findings['critical']),
                'high_findings': len(self.findings['high']) + high_api_keys,
                'medium_findings': len(self.findings['medium']) + medium_api_keys,
                'low_findings': len(self.findings['low']) + low_api_keys,
                'info_findings': len(self.findings['info']),
                'api_keys_found': len(api_keys)
            },
            'findings': self.findings,
            'api_keys': api_keys,
            'tech_stack': tech_stack
        }
        
        if output_format == 'json':
            return json.dumps(report, indent=2)
        else:
            return self.format_text_report(report)
    
    def format_text_report(self, report):
        """Format report as text"""
        output = []
        output.append("=" * 80)
        output.append(f"🔒 SECURITY SCAN REPORT - {report['target'].upper()}")
        output.append("=" * 80)
        output.append(f"📅 Scan Date: {report['scan_date']}")
        output.append("")
        
        # Statistics
        output.append("📊 SCAN STATISTICS")
        output.append("-" * 40)
        output.append(f"🌐 Subdomains Found: {report['statistics']['subdomains_found']}")
        output.append(f"📄 JavaScript Files: {report['statistics']['js_files_found']}")
        output.append(f"🎯 Total Findings: {report['statistics']['total_findings']}")
        output.append(f"🔑 API Keys Found: {report['statistics']['api_keys_found']}")
        output.append("")
        
        # Findings by severity
        output.append("🚨 FINDINGS BY SEVERITY")
        output.append("-" * 40)
        output.append(f"🔴 Critical: {report['statistics']['critical_findings']}")
        output.append(f"🟠 High: {report['statistics']['high_findings']}")
        output.append(f"🟡 Medium: {report['statistics']['medium_findings']}")
        output.append(f"🟢 Low: {report['statistics']['low_findings']}")
        output.append(f"🔵 Info: {report['statistics']['info_findings']}")
        output.append("")
        
        # Explanation of findings
        if report['statistics']['api_keys_found'] > 0:
            output.append("📋 FINDINGS BREAKDOWN:")
            output.append("-" * 40)
            output.append(f"• Nuclei Scan Results: {sum(len(findings) for findings in self.findings.values())}")
            output.append(f"• API Key Exposures: {report['statistics']['api_keys_found']}")
            output.append("")
        
        # Critical Findings
        if report['findings']['critical']:
            output.append("🔴 CRITICAL FINDINGS")
            output.append("-" * 40)
            for finding in report['findings']['critical']:
                output.append(f"Type: {finding['type']}")
                output.append(f"URL: {finding['url']}")
                output.append(f"Details: {finding['details']}")
                output.append("")
        
        # High Findings
        if report['findings']['high']:
            output.append("🟠 HIGH SEVERITY FINDINGS")
            output.append("-" * 40)
            for finding in report['findings']['high']:
                output.append(f"Type: {finding['type']}")
                output.append(f"URL: {finding['url']}")
                output.append(f"Details: {finding['details']}")
                output.append("")
        
        # API Keys Found
        if report['api_keys']:
            output.append("🔑 API KEYS DISCOVERED")
            output.append("-" * 40)
            
            # Group by severity
            high_severity_keys = [k for k in report['api_keys'] if k['severity'] == 'HIGH']
            medium_severity_keys = [k for k in report['api_keys'] if k['severity'] == 'MEDIUM']
            low_severity_keys = [k for k in report['api_keys'] if k['severity'] == 'LOW']
            
            if high_severity_keys:
                output.append("🟠 HIGH SEVERITY API KEYS:")
                output.append("")
                for key_info in high_severity_keys:
                    output.append(f"🔑 Key: {key_info['key']}")
                    output.append(f"🌐 URL: {key_info['url']}")
                    output.append(f"📝 Type: {key_info['type']}")
                    output.append(f"⚠️  Risk: {key_info['description']}")
                    output.append("")
            
            if medium_severity_keys:
                output.append("🟡 MEDIUM SEVERITY API KEYS:")
                output.append("")
                for key_info in medium_severity_keys:
                    output.append(f"🔑 Key: {key_info['key']}")
                    output.append(f"🌐 URL: {key_info['url']}")
                    output.append(f"📝 Type: {key_info['type']}")
                    output.append(f"⚠️  Risk: {key_info['description']}")
                    output.append("")
            
            if low_severity_keys:
                output.append("🟢 LOW SEVERITY API KEYS:")
                output.append("")
                for key_info in low_severity_keys:
                    output.append(f"🔑 Key: {key_info['key']}")
                    output.append(f"🌐 URL: {key_info['url']}")
                    output.append(f"📝 Type: {key_info['type']}")
                    output.append(f"⚠️  Risk: {key_info['description']}")
                    output.append("")
        
        # Medium Findings
        if report['findings']['medium']:
            output.append("🟡 MEDIUM SEVERITY FINDINGS")
            output.append("-" * 40)
            for finding in report['findings']['medium']:
                output.append(f"Type: {finding['type']}")
                output.append(f"URL: {finding['url']}")
                output.append(f"Details: {finding['details']}")
                output.append("")
        
        # Technology Stack
        if report['tech_stack']:
            output.append("🛠️ TECHNOLOGY STACK")
            output.append("-" * 40)
            for url, data in report['tech_stack'].items():
                output.append(f"URL: {url}")
                if data.get('status_code'):
                    output.append(f"Status: {data['status_code']}")
                if data.get('technologies'):
                    output.append(f"Technologies: {', '.join(data['technologies'])}")
                output.append("")
        
        # Security Recommendations
        if report['api_keys']:
            output.append("")
            output.append("🛡️ SECURITY RECOMMENDATIONS")
            output.append("-" * 40)
            output.append("• Move API keys to backend environment variables")
            output.append("• Use API key restrictions in Google Cloud Console")
            output.append("• Implement proper CORS policies")
            output.append("• Consider using Firebase App Check")
            output.append("• Review and rotate exposed API keys")
            output.append("• Implement proper authentication mechanisms")
            output.append("")
        
        output.append("=" * 80)
        output.append("📝 Report generated by R0TBB Security Scanner")
        output.append("=" * 80)
        
        return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description='Generate security reports from R0TBB scan results')
    parser.add_argument('target', help='Target domain or path to scan results')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Determine target directory
    if os.path.isdir(args.target):
        target_dir = args.target
    else:
        # Assume it's a domain and look in bugbounty directory
        bugbounty_dir = Path.home() / "bugbounty"
        target_dir = bugbounty_dir / args.target
    
    if not os.path.exists(target_dir):
        print(f"❌ Error: Target directory not found: {target_dir}")
        sys.exit(1)
    
    # Generate report
    generator = SecurityReportGenerator(target_dir)
    report = generator.generate_report(args.format)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to: {args.output}")
    else:
        print(report)

if __name__ == "__main__":
    main()

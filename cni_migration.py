#!/usr/bin/env python3
"""
CNI Migration Tool - Main entry point

This tool helps assess and facilitate migration from existing Kubernetes CNI solutions
(Flannel, Calico, Weave, etc.) to Cilium.
"""

# Standard library imports
import os
import sys

# Third-party library imports
import click  # CLI framework for creating command-line interfaces
import logging
from rich.console import Console  # Rich text and formatting in the terminal
from rich.logging import RichHandler  # Rich handler for logging

# Local module imports - import the core functionality from the lib directory
from lib.assessment import assess_current_cni  # Module for assessing current CNI configuration
from lib.policy_converter import convert_policies  # Module for converting network policies
from lib.migration_planner import generate_migration_plan  # Module for generating migration plans
from lib.validator import validate_connectivity  # Module for validating connectivity

# Set up logging configuration with Rich formatting
logging.basicConfig(
    level=logging.INFO,  # Default log level
    format="%(message)s",  # Log message format
    datefmt="[%X]",  # Date format for log messages
    handlers=[RichHandler(rich_tracebacks=True)]  # Use Rich for better formatted logs and tracebacks
)
log = logging.getLogger("cni-migration")  # Get a logger for this module
console = Console()  # Create a Rich console for formatted output

@click.group()  # Define a Click command group for organizing sub-commands
@click.option('--debug', is_flag=True, help='Enable debug logging')  # Add a debug flag option
def cli(debug):
    """CNI Migration Tool - Assess and facilitate migration to Cilium"""
    # Enable debug logging if the debug flag is set
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)  # Set root logger to DEBUG level
        log.debug("Debug logging enabled")  # Log that debug mode is enabled

@cli.command()  # Register this function as a sub-command of the CLI group
@click.option('--output-dir', default='./assessment', help='Directory to store assessment results')  # Add output directory option
def assess(output_dir):
    """Assess current CNI configuration and determine migration difficulty"""
    # Display a message indicating the assessment is starting
    console.print("[bold blue]Starting CNI assessment...[/bold blue]")
    try:
        # Call the assessment module to analyze the current CNI configuration
        results = assess_current_cni(output_dir)

        # Display the assessment results to the user
        console.print(f"[bold green]Assessment complete! Results saved to {output_dir}[/bold green]")
        console.print(f"Detected CNI: [bold]{results['cni_type']}[/bold]")
        console.print(f"Migration difficulty: [bold]{results['difficulty']}[/bold]")
        console.print(f"Number of network policies: [bold]{results['policy_count']}[/bold]")
    except Exception as e:
        # Handle any errors that occur during assessment
        console.print(f"[bold red]Error during assessment: {str(e)}[/bold red]")
        sys.exit(1)  # Exit with error code

@cli.command()  # Register this function as a sub-command of the CLI group
@click.option('--source-cni', required=True, type=click.Choice(['calico', 'flannel', 'weave', 'kubenet', 'kindnet']),
              help='Source CNI type')  # Required option to specify the source CNI
@click.option('--input-dir', default='./assessment/policies', help='Directory containing network policies')  # Input directory option
@click.option('--output-dir', default='./converted-policies', help='Directory to store converted policies')  # Output directory option
@click.option('--validate/--no-validate', default=True, help='Validate converted policies')  # Flag to enable/disable validation
@click.option('--apply/--no-apply', default=False, help='Apply converted policies to the cluster')  # Flag to apply policies to cluster
def convert(source_cni, input_dir, output_dir, validate, apply):
    """Convert network policies from source CNI to Cilium format"""
    # Display a message indicating the conversion is starting
    console.print(f"[bold blue]Converting {source_cni} network policies to Cilium format...[/bold blue]")

    # Safety check: Confirm with the user before applying policies to the cluster
    if apply:
        console.print("[bold yellow]Warning: You are about to apply converted policies to your cluster.[/bold yellow]")
        console.print("This may affect existing network connectivity.")
        if not click.confirm("Do you want to continue?"):
            console.print("Conversion cancelled.")
            return

    try:
        # Call the policy converter module to convert the network policies
        result = convert_policies(source_cni, input_dir, output_dir, validate, apply)

        # Display the conversion results to the user
        console.print(f"[bold green]Conversion complete![/bold green]")
        console.print(f"Total policies processed: [bold]{result['total_count']}[/bold]")
        console.print(f"Successfully converted: [bold]{result['converted_count']}[/bold]")

        # Display information about failed conversions if any
        if result['failed_count'] > 0:
            console.print(f"Failed to convert: [bold yellow]{result['failed_count']}[/bold yellow]")

        # Display validation results if validation was enabled
        if validate:
            if result['validation_failed_count'] > 0:
                console.print(f"Failed validation: [bold yellow]{result['validation_failed_count']}[/bold yellow]")
                console.print("See validation errors in: [bold]" + os.path.join(output_dir, 'validation') + "[/bold]")

        # Display information about applied policies if apply was enabled
        if apply:
            console.print(f"Applied to cluster: [bold]{result['applied_count']}[/bold]")

        # Display the locations of output files for reference
        console.print(f"\nOutput files:")
        console.print(f"- Converted policies: [bold]{output_dir}[/bold]")
        console.print(f"- Conversion report: [bold]{os.path.join(output_dir, 'conversion_report.md')}[/bold]")
        console.print(f"- Conversion summary: [bold]{os.path.join(output_dir, 'conversion_summary.json')}[/bold]")

        # Provide recommendations if there were any issues
        if result['failed_count'] > 0 or (validate and result['validation_failed_count'] > 0):
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            console.print("- Review the conversion report for details on failed policies")
            console.print("- Manually fix policies that failed conversion or validation")
            console.print("- Re-run the conversion with the --no-validate option if validation errors are expected")
    except Exception as e:
        # Handle any errors that occur during conversion
        console.print(f"[bold red]Error during conversion: {str(e)}[/bold red]")
        sys.exit(1)  # Exit with error code

@cli.command()  # Register this function as a sub-command of the CLI group
@click.option('--target-cidr', required=True, help='Target CIDR for Cilium (e.g., 10.245.0.0/16)')  # Required option for Cilium CIDR
@click.option('--approach', type=click.Choice(['hybrid', 'multus', 'clean']), default='hybrid',
              help='Migration approach to use')  # Option to select migration approach with default value
@click.option('--output-file', default='./migration-plan.md', help='Output file for migration plan')  # Output file option
def plan(target_cidr, approach, output_file):
    """Generate a step-by-step migration plan"""
    # Display a message indicating the plan generation is starting
    console.print(f"[bold blue]Generating migration plan using {approach} approach...[/bold blue]")
    try:
        # Call the migration planner module to generate the migration plan
        generate_migration_plan(target_cidr, approach, output_file)

        # Display a success message with the output file location
        console.print(f"[bold green]Migration plan generated and saved to {output_file}[/bold green]")
    except Exception as e:
        # Handle any errors that occur during plan generation
        console.print(f"[bold red]Error generating migration plan: {str(e)}[/bold red]")
        sys.exit(1)  # Exit with error code

@cli.command()  # Register this function as a sub-command of the CLI group
@click.option('--phase', type=click.Choice(['pre', 'during', 'post']), default='pre',
              help='Migration phase to validate')  # Option to specify the migration phase
@click.option('--source-cni', help='Source CNI type (required for during/post validation)')  # Option for source CNI
@click.option('--target-cidr', help='Target CIDR for Cilium (required for during validation)')  # Option for target CIDR
@click.option('--report-dir', default='./validation-reports', help='Directory to store validation reports')  # Report directory option
def validate(phase, source_cni, target_cidr, report_dir):
    """Validate connectivity and policy enforcement"""
    # Create a dictionary to map phase codes to human-readable descriptions
    phase_desc = {"pre": "pre-migration", "during": "during migration", "post": "post-migration"}

    # Display a message indicating the validation is starting
    console.print(f"[bold blue]Validating connectivity ({phase_desc[phase]})...[/bold blue]")

    # Validate that required parameters are provided based on the phase
    if phase in ['during', 'post'] and not source_cni:
        console.print("[bold red]Error: --source-cni is required for during/post validation[/bold red]")
        sys.exit(1)  # Exit with error code

    if phase == 'during' and not target_cidr:
        console.print("[bold red]Error: --target-cidr is required for during validation[/bold red]")
        sys.exit(1)  # Exit with error code

    # Create the report directory if it doesn't exist
    os.makedirs(report_dir, exist_ok=True)

    try:
        # Call the validator module to validate connectivity
        results = validate_connectivity(phase, source_cni, target_cidr)

        # Display the validation results based on success or failure
        if results['success']:
            # All tests passed
            console.print(f"[bold green]Validation successful![/bold green]")
            console.print(f"Connectivity tests passed: [bold]{results['passed_tests']}/{results['total_tests']}[/bold]")
        else:
            # Some tests failed
            console.print(f"[bold yellow]Validation issues detected![/bold yellow]")
            console.print(f"Connectivity tests passed: [bold]{results['passed_tests']}/{results['total_tests']}[/bold]")

            # Group issues by test type for better organization
            issue_categories = {}
            for result in results['results']:
                if not result['success']:
                    # Extract the category from the test name (e.g., "Pod-to-Pod" -> "Pod")
                    category = result['name'].split(' ')[0]
                    if category not in issue_categories:
                        issue_categories[category] = []
                    issue_categories[category].append(result['message'])

            # Display issues grouped by category
            for category, issues in issue_categories.items():
                console.print(f"[bold]{category} Issues:[/bold]")
                for issue in issues:
                    console.print(f"  - {issue}")

        # Display the location of the detailed report
        console.print(f"\nDetailed validation report saved to: [bold]{report_dir}[/bold]")

        # Provide phase-specific recommendations if there were issues
        if phase == 'pre' and not results['success']:
            # Recommendations for pre-migration issues
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            console.print("- Fix connectivity issues before proceeding with migration")
            console.print("- Ensure all pods can communicate with each other and with services")
            console.print("- Verify DNS resolution is working correctly")

        elif phase == 'during' and not results['success']:
            # Recommendations for during-migration issues
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            console.print("- Check Cilium configuration for cross-CNI communication")
            console.print("- Verify that the CiliumNodeConfig is correctly applied")
            console.print("- Ensure both CNIs are using different CIDRs")
            console.print("- Check for firewall rules that might be blocking traffic")

        elif phase == 'post' and not results['success']:
            # Recommendations for post-migration issues
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            console.print("- Verify that all nodes have been migrated to Cilium")
            console.print("- Check that network policies have been correctly converted")
            console.print("- Ensure the old CNI has been completely removed")
            console.print("- Consider rebooting nodes to clean up any remnants")

    except Exception as e:
        # Handle any errors that occur during validation
        console.print(f"[bold red]Error during validation: {str(e)}[/bold red]")
        sys.exit(1)  # Exit with error code

# Entry point for the script - only execute if run directly (not imported)
if __name__ == '__main__':
    cli()  # Call the main CLI function

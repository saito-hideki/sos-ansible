#!/usr/bin/env python
"""
sos_ansible, main program
"""

import argparse
import logging
import os
import sys
import inquirer
from modules.file_handling import read_policy, process_rule, validate_tgt_dir
from modules.locating_sos import LocateReports
from modules.config_manager import load_config


def get_user_input(sos_directory):
    """Select workdir"""
    choice = os.listdir(sos_directory)
    questions = [
        inquirer.List("case", message="Choose the sos directory", choices=choice),
    ]
    return inquirer.prompt(questions)["case"]


def data_input(sos_directory, rules_file, user_choice):
    """
    Load the external sosreport and policy rules
    """
    logging.info("Validating sosreports on target directory: %s", sos_directory)
    report_data = LocateReports()
    node_data = report_data.run({sos_directory}, user_choice)
    logging.info("Validating rules in place: %s", rules_file)
    curr_policy = read_policy(rules_file)
    return node_data, curr_policy


def rules_processing(node_data, curr_policy, user_choice):
    """
    Read the rules.json file and load it on the file_handling modules for processing.
    """
    div = "\n--------\n"
    for hosts in node_data:
        hostname = hosts["hostname"]
        path = hosts["path"]
        analysis_summary = (
            f"Summary\n{hostname}:{div}Controller Node: {hosts['controller']}{div}"
        )
        logging.info("Processing node %s:", hostname)
        for rules in curr_policy:
            match_count = int()
            iterator = curr_policy[rules]
            for files in iterator["files"]:
                to_read = f"{path}/{iterator['path']}/{files}"
                query = iterator["query"].replace(", ", "|")
                result_count = process_rule(
                    hostname, user_choice, rules, to_read, query
                )
                match_count += result_count
            analysis_summary += f"{rules}: {match_count}\n"
        logging.critical(analysis_summary)


def main():
    """
    Main function from sos_ansible. This will process all steps for sosreports reading
    """
    config = load_config()
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Directory containing sosreports",
        required=False,
        default="",
    )
    parser.add_argument(
        "-r",
        "--rules",
        type=str,
        help="Rules file with full path",
        required=False,
        default="",
    )
    parser.add_argument(
        "-c",
        "--case",
        type=str,
        help="Directory number to which the sosreport was extracted",
        required=False,
    )
    params = parser.parse_args()
    if params.directory:
        sos_directory = params.directory
    else:
        sos_directory = os.path.abspath(config.get("files", "source"))
    if params.rules:
        rules_file = os.path.abspath(params.rules)
    else:
        rules_file = os.path.abspath(config.get("files", "rules"))

    logging.basicConfig(
        filename="sos-ansible.log",
        format="%(levelname)s:%(message)s",
        level=logging.DEBUG,
    )

    console = logging.StreamHandler()
    console.setLevel(logging.CRITICAL)
    logging.getLogger("").addHandler(console)

    # In order to allow both container and standard command line usage must check for env
    try:
        if os.environ["IS_CONTAINER"]:
            if not params.case:
                logging.error("A case number must be used if running from a container")
                sys.exit("A case number must be used if running from a container")
    except KeyError:
        pass
    # if case number is not provided prompt if provided just use it
    if os.path.isdir(sos_directory) and not params.case:
        user_choice = get_user_input(sos_directory)
    elif os.path.isdir(sos_directory) and params.case:
        user_choice = params.case
    else:
        logging.error(
            "The selected directory %s doesn't exist."
            "Select a new directory and try again.",
            sos_directory,
        )
        sys.exit(1)
    validate_tgt_dir(user_choice)
    node_data, curr_policy = data_input(sos_directory, rules_file, user_choice)
    if not node_data:
        logging.error(
            "No sosreports found, please review the directory %s", sos_directory
        )
        sys.exit(1)
    logging.info(node_data)
    rules_processing(node_data, curr_policy, user_choice)


if __name__ == "__main__":
    main()

from colorama import init, Fore, Back, Style
import sys
import os.path
import json
import pprint
import re
import argparse

pp = pprint.PrettyPrinter(indent=2, width=200)

ASM_FIXER_FILE_PREFIX = 'asmf-'
DEFAULT_CONFIG_FILE = ASM_FIXER_FILE_PREFIX + 'config.json'
DEFAULT_BACKUP_FILE = ASM_FIXER_FILE_PREFIX + 'backup.asm'
DEFAULT_CONFIG = {
    '_CONFIG_VERSION': '0.7',
    'fix_indents': True,
    'tab_size': 2,

    'fix_file_width': True,
    'file_width': 80,
    'long_comment_indent_amount': 2,

    'fix_capitalization': True,
    'fix_blank_lines': True,

    'align_comments': True,
    'align_data_comments': True,
    'align_data_comments_separately': True,
    'min_comment_spacing': 3,

    'align_code_section': True,
    'min_instruction_operand_spacing': 3,
    'add_spaces_between_operands': True,

    'align_data_section': True,
    'align_code_and_data_together': False,
    'min_data_directive_spacing': 2,
    'min_data_initial_value_spacing': 2,
    'add_spaces_between_initial_values': True,

    # TODO: Include?
    # 'header_comment_report': True,
    # 'logic_efficiency_report': True,
    # 'required_code_report': True,

    'align_header_comments': True,
}


def main():
    init(autoreset=True)

    # Check command-line arguments
    parser = argparse.ArgumentParser(description='Reformats an assembly file according to Baylor CSI2334 standards.')
    parser.add_argument('file', help='the file to fix')
    parser.add_argument('-c', '--config', '--config-file', dest='CONFIG_FILE', help=f'the name of configuration file to use (default: {DEFAULT_CONFIG_FILE})', default=DEFAULT_CONFIG_FILE)
    parser.add_argument('-o', '--output', '--output-file', dest='OUTPUT_FILE', help='output to OUTPUT_FILE instead of STDOUT')
    parser.add_argument('-x', '--overwrite', help='overwrite the input file (sets --safe; overrides --output)', action='store_true')
    parser.add_argument('-s', '--safe', '--backup-mode', help='generate a backup file (not required if --backup is set)', action='store_true')
    parser.add_argument('-u', '--unsafe', '--no-backup', help='do not use a backup file, when used with --overwrite (not recommended)', action='store_true')
    parser.add_argument('-b', '--backup', '--backup-file', dest='BACKUP_FILE', help=f'the name of the backup file (default: {DEFAULT_BACKUP_FILE})')
    args = parser.parse_args()

    # Process command-line arguments
    file_name = args.file
    config_file_name = args.CONFIG_FILE
    backup_file_name = args.BACKUP_FILE or DEFAULT_BACKUP_FILE
    output_file_name = args.OUTPUT_FILE if not args.overwrite else args.file
    safe_mode = args.safe or args.BACKUP_FILE is not None or (args.overwrite and not args.unsafe)
    config = {}

    # Process config
    if not os.path.isfile(config_file_name):
        config = DEFAULT_CONFIG
        with open(config_file_name, 'w+') as new_config_file:
            json.dump(config, new_config_file, indent=2)
    else:
        with open(config_file_name, 'r') as config_file:
            config = json.loads(config_file.read())

        if config['_CONFIG_VERSION'] != DEFAULT_CONFIG['_CONFIG_VERSION']:
            print(Fore.YELLOW + 'Warning: config file out of date; updating...')
            new_config = DEFAULT_CONFIG.copy()
            for key in config.keys():
                if key in new_config:
                    new_config[key] = config[key]
            new_config['_CONFIG_VERSION'] = DEFAULT_CONFIG['_CONFIG_VERSION']
            with open(config_file_name, 'w') as config_file:
                json.dump(new_config, config_file, indent=2)
            config = new_config

    # Read file
    with open(file_name, 'r') as file:
        lines = file.readlines()
    if safe_mode:
        with open(backup_file_name, 'w+') as file:
            file.write(''.join(lines))

    # Parse lines of file
    tokens = []
    for line in lines:
        # Preprocess Line
        indent = re.match(r'^[ \t]*', line).group(0).replace('\t', ' ' * config['tab_size'])
        line = line.strip()

        # Blank Line
        if len(line) == 0:
            tokens.append({
                'type': 'blank_line'
            })
        # Comment Extension
        elif line.startswith(';  '):
            tokens.append({
                'type': 'comment',
                'subtype': 'extension',
                'value': line[1:].strip()
            })
        # Header Comment
        elif re.search(r';.*(Author|Assignment|Date).*:', line, re.IGNORECASE):
            tokens.append({
                'type': 'comment',
                'subtype': 'header',
                'field': line[1:line.find(':')].strip(),
                'value': line[line.find(':') + 1:].strip()
            })
        # Full-line Comment
        elif line.startswith(';'):
            tokens.append({
                'type': 'comment',
                'subtype': 'full_line',
                'value': line[1:].strip()
            })
        # Directive
        elif line.startswith('.') or line.startswith('INCLUDE') or line.startswith('END', re.IGNORECASE):
            tokens.append({
                'type': 'directive',
                'value': re.match(r'\.?([a-zA-Z0-9.] ?)+', line).group(0).strip(),
                'comment': line[line.find(';') + 2:] if line.find(';') > 0 else None
            })
        # Data Value
        elif re.search(r'^([a-zA-Z_][a-zA-Z0-9_]+)[ \t]+(BYTE|D?Q?WORD)[ \t]+(([0-9a-zA-Z,()?] ?|".+")+)', line, re.IGNORECASE):
            match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]+)[ \t]+(BYTE|D?Q?WORD)[ \t]+(([0-9a-zA-Z,()?] ?|".+")+)', line, re.IGNORECASE)
            tokens.append({
                'type': 'data',
                'label': match.group(1),
                'directive': match.group(2),
                'value': match.group(3).strip() if match.group(3) is not None else None,
                'comment': line[line.find(';') + 2:] if line.find(';') > 0 else None
            })
        # Procedure
        elif re.search(r'^([a-zA-Z_][a-zA-Z0-9_]*)[ \t]+(PROC|ENDP)', line):
            match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)[ \t]+(PROC|ENDP)', line)
            tokens.append({
                'type': 'procedure',
                'label': match.group(1),
                'value': match.group(2),
                'comment': line[line.find(';') + 2:] if line.find(';') > 0 else None
            })
        # Instruction/Macro
        elif re.search(r'^([a-zA-Z][a-zA-Z0-9]*)([ \t]+(([0-9a-zA-Z,] ?)+))?', line):
            match = re.search(r'^([a-zA-Z][a-zA-Z0-9]*)([ \t]+(([0-9a-zA-Z,] ?)+))?', line)
            tokens.append({
                'type': 'instruction',
                'mnemonic': match.group(1),
                'operands': match.group(3).strip() if match.group(3) is not None else None,
                'comment': line[line.find(';') + 2:] if line.find(';') > 0 else None
            })
        # Unrecognized
        else:
            tokens.append({
                'type': 'error',
                'error': 'Unrecognized Token',
                'value': line
            })

        # If fix_indents is disabled, add the indent back
        if not config['fix_indents']:
            tokens[-1]['indent'] = indent

    # Process Tokens
    max_field_size = 0
    max_label_size = 0
    max_size_size = 0
    max_mnemonic_size = 0
    for i in range(len(tokens)):
        if config['fix_file_width'] and i > 0 and tokens[i]['type'] == 'comment' and tokens[i]['subtype'] == 'extension':
            if tokens[i - 1]['type'] == 'comment':
                tokens[i - 1]['value'] += ' ' + tokens[i]['value']
            else:
                tokens[i - 1]['comment'] = (tokens[i - 1]['comment'] or '') + ' ' + tokens[i]['value']
            tokens[i]['type'] = 'to_remove'
        if config['fix_capitalization']:
            if 'mnemonic' in tokens[i]:
                tokens[i]['mnemonic'] = tokens[i]['mnemonic'].lower()
            if 'directive' in tokens[i]:
                tokens[i]['directive'] = tokens[i]['directive'].upper()
            if tokens[i]['type'] == 'directive':
                tokens[i]['value'] = tokens[i]['value'].upper()
        if tokens[i]['type'] == 'error':
            print(Fore.RED + f'Error on line {i+1}:' + tokens[i]['error'] + '\n  ' + tokens[i]['value'])
        elif tokens[i]['type'] == 'data':
            max_label_size = max(max_label_size, len(tokens[i]['label']))
            max_size_size = max(max_size_size, len(tokens[i]['directive']))
            if config['add_spaces_between_initial_values'] and tokens[i]['value'] is not None:
                tokens[i]['value'] = ', '.join(re.split(f', ?', tokens[i]['value']))
        elif tokens[i]['type'] == 'instruction':
            max_mnemonic_size = max(max_mnemonic_size, len(tokens[i]['mnemonic']))
            if config['add_spaces_between_operands'] and tokens[i]['operands'] is not None:
                tokens[i]['operands'] = ', '.join(re.split(f', ?', tokens[i]['operands']))
        elif config['fix_blank_lines'] and i > 0 and tokens[i]['type'] == 'blank_line':
            if tokens[i - 1]['type'] == 'blank_line':
                tokens[i]['type'] = 'to_remove'
        elif tokens[i]['type'] == 'comment' and tokens[i]['subtype'] == 'header':
            max_field_size = max(max_field_size, len(tokens[i]['field']))

    if config['align_code_and_data_together']:
        max_label_size = max_mnemonic_size = max(max_label_size, max_mnemonic_size)
        config['min_instruction_operand_spacing'] = config['min_data_directive_spacing'] = max(config['min_instruction_operand_spacing'], config['min_data_directive_spacing'])

    tokens = [x for x in tokens if x['type'] != 'to_remove']

    # Parse Tokens
    parsed_tokens = []
    max_string_size = 0
    max_data_string_size = 0
    indent_counter = 0
    for token in tokens:
        if token['type'] == 'comment':
            if token['subtype'] == 'header':
                if config['align_header_comments']:
                    line = f'; {token["field"] + ":"}'.ljust(len('; : ') + max_field_size) + token['value']
                else:
                    line = f'; {token["field"]}: {token["value"]}'
                if config['fix_file_width'] and len(line) > config['file_width']:
                    last_space = line.rfind(' ', 0, config['file_width'])
                    parsed_tokens.append(line[:last_space])
                    parsed_tokens.append('; '.ljust(len('; : ') + max_field_size) + line[last_space + 1:])
                else:
                    parsed_tokens.append(line)
            elif token['subtype'] == 'full_line':
                parsed_tokens.append({
                    'str': f'; {token["value"]}',
                    'comment': None
                })
        elif token['type'] == 'blank_line':
            parsed_tokens.append('')
        elif token['type'] == 'directive':
            parsed_tokens.append({
                'str': token['value'],
                'comment': token['comment']
            })
        elif token['type'] == 'directive':
            parsed_tokens.append({
                'str': token['value'],
                'comment': token['comment']
            })
        elif token['type'] == 'data':
            parsed_tokens.append({
                'str': token['label'].ljust((max_label_size if config['align_data_section'] else len(token['label'])) + config['min_data_directive_spacing']) + token['directive'].ljust(max_size_size + config['min_data_initial_value_spacing']) + token['value'],
                'comment': token['comment'],
                'data': True
            })
            if config['align_data_comments'] and config['align_data_comments_separately']:
                max_data_string_size = max(max_data_string_size, len(parsed_tokens[-1]['str']))
        elif token['type'] == 'procedure':
            parsed_tokens.append({
                'str': token['label'] + ' ' + token['value'],
                'comment': token['comment']
            })
            if token['value'] == 'PROC':
                indent_counter += 1
            else:
                indent_counter -= 1
        elif token['type'] == 'instruction':
            parsed_tokens.append({
                'str': token['mnemonic'].ljust((max_mnemonic_size if config['align_code_section'] else len(token['mnemonic'])) + config['min_instruction_operand_spacing']) + (token['operands'] or ''),
                'comment': token['comment']
            })

        if not config['fix_indents']:
            if type(parsed_tokens[-1]) is dict:
                parsed_tokens[-1]['str'] = token['indent'] + parsed_tokens[-1]['str']
            else:
                parsed_tokens[-1] = token['indent'] + parsed_tokens[-1]
        else:
            if type(parsed_tokens[-1]) is dict:
                parsed_tokens[-1]['str'] = ' '*(config['tab_size'] * indent_counter) + parsed_tokens[-1]['str']
            else:
                parsed_tokens[-1] = ' ' * (config['tab_size'] * indent_counter) + parsed_tokens[-1]

        if ((type(parsed_tokens[-1]) is dict and token['type'] != 'data') or (token['type'] == 'data' and config['align_data_comments'] and not config['align_data_comments_separately'])) and (token['type'] != 'comment' or token['subtype'] != 'full_line'):
            max_string_size = max(max_string_size, len(parsed_tokens[-1]['str']))

    # Print the output
    # with sys.stdout as output_file:
    if output_file_name is None:
        output_file = sys.stdout
    else:
        output_file = open(output_file_name, 'w')
    for line in parsed_tokens:
        if type(line) is str:
            print(line, file=output_file)
        else:
            if (config['align_comments'] and 'data' not in line) or (config['align_comments'] and 'data' in line and config['align_data_comments'] and not config['align_data_comments_separately']):
                output_string = line['str'].ljust(max_string_size + config['min_comment_spacing']) + ('; ' + line['comment'] if line['comment'] else '')
            elif 'data' in line and config['align_data_comments'] and config['align_data_comments_separately']:
                output_string = line['str'].ljust(max_data_string_size + config['min_comment_spacing']) + ('; ' + line['comment'] if line['comment'] else '')
            else:
                output_string = line['str'] + ' '*config['min_comment_spacing'] + ('; ' + line['comment'] if line['comment'] else '')

            output_string = output_string.rstrip()
            if not config['fix_file_width'] or len(output_string) <= config['file_width']:
                print(output_string, file=output_file)
            else:
                last_space = output_string.rfind(' ', 0, config['file_width'])
                print(output_string[:last_space], file=output_file)
                print('; '.rjust(output_string.find(';') + 2) + ' '*config['long_comment_indent_amount'] + output_string[last_space + 1:])
    output_file.close()

          
if __name__ == "__main__":
    sys.exit(main())

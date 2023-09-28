import os, argparse, operator, itertools, subprocess, pwd, datetime, logging
from typing import Iterable, Tuple, Generator

import jinja2, tqdm

import scan_unused
from scan_unused.core import Node, Tree
from scan_unused.utils import size_getter_str, get_atime_day_offset

def gen_email(template, tree: Node, nodes: Iterable[Node], owner: str, args) -> Tuple[str, Generator[str, None, None]]:
    '''
    Convert warning parameters to email address and generator based on template.
    '''
    data = {
        'owner': owner,
        'nodes_dir': os.path.abspath(tree.root.name),
        'nodes_size': size_getter_str(sum([x.size for x in nodes])),
        'nodes_count': len(nodes),
        'nodes': nodes,
        'args': args,
    }
    gen = template.generate(**data)
    to = next(gen, None)
    if to and to.startswith('To: '):
        def _gen_full():
            yield to
            yield from gen
        return to.split(':', 1)[1].strip(), _gen_full()
    raise Exception('Template must start with email headers i.e. To:')

def main():
    parser = argparse.ArgumentParser(
                prog='scan-unused',
                description='Find, delete and notify users of unused files on a shared filesystem')
    parser.add_argument('directory')
    parser.add_argument('--days', metavar='N', type=int, default=3, help='number of days after which a file is considered old (default 3)')
    parser.add_argument('--force', action='store_true', help='Force yes for confirmation (dangerous)')
    parser.add_argument('--email-domain', help='Send an email to each owner@domain about future deletions (modify template for more control)')
    parser.add_argument('--email-days', type=int, help='if provided, only mention files that will be deleted in this exact number of days')
    parser.add_argument('--email-limit', type=int, default=50, help='limit number of paths in emails')
    parser.add_argument('--email-template', type=int, help='path to override jinja2 template')
    parser.add_argument('--email-whitelist', nargs='+', help='limit users that can receive emails')
    parser.add_argument('--dryrun', action='store_true', help='Print files/emails that would have been deleted/sent')
    args = parser.parse_args()

    offset = get_atime_day_offset(args.directory)
    if offset:
        logging.warn(f'Directory "{args.directory}" mounted with relatime, days increased by {offset}')
        args.days += offset

    size_getter = operator.attrgetter('size')
    owner_getter = operator.attrgetter('owner')

    # Construct in-memory tree of all files/folders
    tree = Tree.from_dir(args.directory)

    # Delete unused nodes
    nodes_to_delete = list(tree.iter_nodes_unused(args.days))
    should_delete = args.force
    if args.dryrun:
        print('Would have deleted:')
        print(*sorted(nodes_to_delete, key=size_getter, reverse=True), sep='\n')

        print('\nRecently accessed files:')
        keep_files = list(tree.iter_nodes(lambda n: not n.is_folder and n.last_access >= (datetime.datetime.now() - datetime.timedelta(days=args.days)).timestamp()))
        print(*sorted(keep_files, key=size_getter, reverse=True), sep='\n')
    else:
        print('Deleting:')
        print(*sorted(nodes_to_delete, key=size_getter, reverse=True), sep='\n')
        
        # Ask user to confirm deletion
        while not should_delete:
            answer = input('continue (yes/no)?\n')
            if answer.lower() in ['yes']: should_delete = True
            elif answer.lower() in ['n', 'no']: break

        if should_delete:
            print('Deleting, do not interrupt...')
            del_bar = tqdm.tqdm(total=len(nodes_to_delete), desc='Deleting')
            for i, _ in enumerate(Tree.delete_nodes(nodes_to_delete)):
                del_bar.update(i)

    # Generate future warning emails for each user
    if args.email_domain:
        # Load user-provided or default email template
        template_paths = [f'{scan_unused.__path__[0]}/templates']
        template_name = 'example.html'
        if args.email_template: 
            template_paths.append(os.path.dirname(os.path.abspath(os.path.expanduser(args.email_template)))) 
            template_name = os.path.basename(args.email_template)
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, loader=jinja2.FileSystemLoader([f'{scan_unused.__path__[0]}/templates'] + ([args.email_template] if args.email_template else [])))
        template = env.get_template(template_name)

        if args.email_days:
            nodes_to_email = list(tree.iter_nodes_unused(args.days, args.email_days))
        else:
            nodes_to_email = list(tree.iter_nodes_unused(args.days, 1))
        for owner_id, node_group in tqdm.tqdm(itertools.groupby(sorted(nodes_to_email, key=owner_getter), owner_getter), desc='Emails'):
            owner = pwd.getpwuid(owner_id).pw_name
            if args.email_whitelist and owner not in args.email_whitelist: continue
            addr, body_chunks = gen_email(template, tree, list(node_group), owner, args)
            if args.dryrun:
                print(f'Would have emailed: {addr}\n\t', end='')
                for chunk in body_chunks:
                    print(chunk.replace('\n', '\n\t'), end='')
                print()
            else:
                p = subprocess.Popen(['sendmail', '-oi', addr], stdin=subprocess.PIPE)
                for chunk in body_chunks:
                    p.stdin.write(chunk.encode())
                p.stdin.close()
                p.wait()
                print(f'Emailed {addr}' if p.returncode == 0 else f'Failed to email {addr}')

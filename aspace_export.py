from __future__ import print_function
import argparse
from asnake.aspace import ASpace
from asnake.jsonmodel import JSONModelObject
import asnake.logging
from functools import partial
import logging

asnake.logging.setup_logging(level='INFO')

class Empty (object):
    '''simple class that returns itself for when any non-existent attribute is requested'''
    def __init__(self, return_string=''):
        self.return_string = return_string
    def __getattr__(self, item):
        return(self)
    def __str__(self):
        return self.return_string
    def __repr__(self):
        return '#<Empty>'

# monkey patch JSONModelObject.__getattr__ to be more lenient
JSONModelObject.__getattr_orig__ = JSONModelObject.__getattr__
def __getattr_override__(*args, **kwargs):
    try:
        obj = JSONModelObject.__getattr_orig__(*args, **kwargs)
    except AttributeError as e:
        obj = Empty('')
        logging.warning('{}: replacing with {!r}'.format(e, obj))
    return obj
JSONModelObject.__getattr__ = __getattr_override__


# RG.14.090 Series 2 (Loose Issues)
# http://aspace.library.jhu.edu:8080/resources/989#tree::archival_object_123452
# http://aspace.library.jhu.edu:8089/repositories/3/archival_objects/123452
# {{as_api_ep}}/repositories/{{as_repo_spcoll}}/archival_objects/123452

repo_num = 3
ao_num = 123452
base_ao_ref = '/repositories/{repo}/archival_objects/{ao}'.format(repo=repo_num, ao=ao_num)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fields', dest='fields', required=True,
                        help='a comma-separated list of fields in dot notation')
    parser.add_argument('-d', '--depth', dest='depth', default=-1, type=int,
                        help='number of generations of descendants (a negative value means unlimited)')
    parser.add_argument('refs', nargs='+', help='a list of object URIs')
    args = parser.parse_args()
    field_names = args.fields.split(',')
    recursion_depth = args.depth if args.depth >= 0 else None

    #field_names = ['repository.uri', 'parent.uri', 'uri', 'date',  'level', 'ref_id', 'title']
    emit = partial(emitter3, field_names=field_names, field_sep=' <-> ',
                   get_values=partial(value_dict, templates=template_dict(field_names)))
    record_generator = partial(recursive_depth_first_from, max_depth=recursion_depth)

    aspace = ASpace()

    for ref in args.refs:
        obj = aspace.from_uri(ref)
        for record in do_process_with_objects(emit, record_generator(obj)):
            print('record: {}'.format(record))


def do_process_with_objects(do_process, with_objects):
    for o in with_objects:
        # print('{}processing me: {}'.format('> ', o.uri))
        yield from do_process(o)


def emitter3(obj, get_values=None, field_names=None, field_sep=','):
    values = get_values(get_fields(obj))
    row_string = field_sep.join([values[f] for f in field_names])
    # print(row_string)
    yield values


def template_dict(field_names):
    return {name: '{{0.{}}}'.format(name) for name in field_names}


def value_dict(obj, templates=None):
    return {k: v.format(obj) for k, v in templates.items()}


def recursive_depth_first_from(top, include_top=True, max_depth=None, _depth=0):
    '''generator - yield objects recursively, depth-first'''
    if include_top:
        yield top
    if max_depth is None or _depth < max_depth:
        if top.jsonmodel_type in ['resource']:
            top = top.tree
        for child in top.children:
            # always include child objects (include_top=True)
            yield from recursive_depth_first_from(child, include_top=True, max_depth=max_depth, _depth=_depth + 1)


def get_fields(obj):
    obj.date = format_date(obj.dates[0].json(), date_sep='-') if len(obj.dates) > 0 else None
    return obj


def format_date(date_obj, date_sep='-'):
    if 'expression' in date_obj:
        return date_obj['expression']
    elif date_obj['date_type'] == 'single':
        return date_obj['begin']
    elif date_obj['date_type'] == 'inclusive':
        return date_sep.join([date_obj['begin'], date_obj['end']])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        logging.warning('process terminated by user')
        exit(1)

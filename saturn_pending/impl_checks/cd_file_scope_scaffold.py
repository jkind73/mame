"""Declaration-only adapters for extracted held-window methods; no fixture expectations."""
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def extend(head, functions, source):
    declarations=[]
    if '::read_new_dir(uint32_t fileno, uint8_t input)' in source:
        head=head.replace('void read_new_dir(uint32_t);','void read_new_dir(uint32_t,uint8_t=0xff);')
    setup='void saturn_cd_hle_device::cd_setup_directory_filter('
    if 'cd_setup_directory_filter(' in functions:
        if 'struct filterT' not in head:
            from pathlib import Path
            header=(Path(__file__).resolve().parents[2]/'src/mame/sega/saturn_cd_hle.h').read_text()
            declarations.append(extract(header,'struct filterT')+';')
        if 'filterT filters[' not in head:
            declarations.append('filterT filters[24]{};')
        if 'cd_setup_directory_filter(' not in head:
            declarations.append('void cd_setup_directory_filter(uint8_t,const direntryT &);')
        if setup not in functions:
            functions+='\n'+extract(source,setup)
    if 'MAX_FILTERS' in functions and 'MAX_FILTERS' not in head:
        head='constexpr unsigned MAX_FILTERS=24;\n'+head
    if 'm_file_scope_start' not in head:
        declarations.append('uint32_t m_file_scope_start=2;')
    if 'm_file_info_words' not in head:
        declarations.append('uint16_t m_file_info_words=0;')
    if 'curdir' not in head:
        declarations.append('std::vector<int> curdir;')
    for result,name,args in [('uint32_t','cd_file_info_count',''),('bool','cd_file_info_held','uint32_t file_id')]:
        if name not in head:
            declarations.append(f'{result} {name}({args}) const;')
        signature=f'{result} saturn_cd_hle_device::{name}('
        if signature in source and signature not in functions:
            functions+='\n'+extract(source,signature)
    if 'cr_standard_return(' in functions and 'cr_standard_return' not in head:
        declarations.append('void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}')
    if 'CD_STAT_REJECT' in functions and 'CD_STAT_REJECT' not in head:
        head='constexpr unsigned CD_STAT_REJECT=0xff00;\n'+head
    at=head.rfind('};')
    assert at>=0
    head='#include <algorithm>\n#include <vector>\n#include <cassert>\n'+head[:at]+'\n'+'\n'.join(declarations)+'\n'+head[at:]
    return head,functions

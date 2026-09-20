"""Declarations for extracted converter-control dependencies; no assertion edits.

Legacy data/transfer mocks without converter state report inactive. The dedicated
range probe replaces that stub with an interval-clocked sink. Neither is native
CD-DA rendering or sample/save qualification.
"""
def extract(text, signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def extend(head, functions, source):
    declarations=[]
    if 'BFUL' in functions and 'BFUL' not in head:
        head='constexpr unsigned BFUL=8;\n'+head
    if 'buffull_temp_pause' in functions and 'buffull_temp_pause' not in head:
        declarations.append('bool buffull_temp_pause=false;')
    sig='void saturn_cd_hle_device::cd_update_cdda()'
    if 'cd_update_cdda(' in functions:
        if 'void cd_update_cdda(' not in head:
            declarations.append('void cd_update_cdda();')
        if sig not in functions:
            functions+='\n'+extract(source,sig)
    for name in ('cd_scan_step', 'cd_scan_audio'):
        sig=f'void saturn_cd_hle_device::{name}()'
        if name+'(' in functions:
            if 'void '+name+'(' not in head:
                declarations.append(f'void {name}();')
            if sig not in functions:
                functions+='\n'+extract(source,sig)
    if 'CD_STAT_SCAN' in functions and 'CD_STAT_SCAN' not in head:
        head='constexpr unsigned CD_STAT_SCAN=0x500;\n'+head
    for field,kind,value in [('m_play_start_fad','uint32_t','150'),('m_play_end_fad','uint32_t','150'),('m_play_range_valid','bool','false'),('m_scan_reverse','bool','false'),('m_scan_audible','bool','false')]:
        if field in functions and field not in head:
            declarations.append(f'{kind} {field}={value};')
    if 'm_cdda->audio_active()' in functions:
        if 'm_cdda' not in head:
            declarations.append('struct Audio{bool audio_active(){return false;}void stop_audio(){}void set_output_gain(int,double){}}audio;Audio *m_cdda=&audio;')
        else:
            audio=extract(head,'struct Audio')
            if 'audio_active(' not in audio:
                value='playing' if 'bool playing=' in audio else 'false'
                head=head.replace(audio,audio[:-1]+f' bool audio_active(){{return {value};}}'+'}',1)
    if 'set_output_gain(' in functions and 'struct Audio' in head:
        audio=extract(head,'struct Audio')
        if 'set_output_gain(' not in audio:
            head=head.replace(audio,audio[:-1]+' void set_output_gain(int,double){}'+'}',1)
    if 'get_last_track(' in source and 'struct Media' in head and 'get_last_track(' not in head:
        media=extract(head,'struct Media')
        # Authored drive-address TOC has an explicit lead-out element. Older
        # file-only API mocks have no TOC; 99 is only a dependency placeholder.
        count='std::size(starts)-1' if 'unsigned starts[]' in media else '99'
        head=head.replace(media,media[:-1]+f' int get_last_track(){{return {count};}}'+'}',1)
    device=extract(head,'struct saturn_cd_hle_device')
    head=head.replace(device,device[:-1]+'\n'+'\n'.join(declarations)+'\n}',1)
    return '#include <algorithm>\n'+head,functions

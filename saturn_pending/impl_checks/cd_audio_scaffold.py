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
    sig='void saturn_cd_hle_device::cd_update_cdda()'
    if 'cd_update_cdda(' in functions:
        if 'void cd_update_cdda(' not in head:
            declarations.append('void cd_update_cdda();')
        if sig not in functions:
            functions+='\n'+extract(source,sig)
    if 'm_cdda->audio_active()' in functions:
        if 'm_cdda' not in head:
            declarations.append('struct Audio{bool audio_active(){return false;}void stop_audio(){}}audio;Audio *m_cdda=&audio;')
        else:
            audio=extract(head,'struct Audio')
            if 'audio_active(' not in audio:
                value='playing' if 'bool playing=' in audio else 'false'
                head=head.replace(audio,audio[:-1]+f' bool audio_active(){{return {value};}}'+'}',1)
    device=extract(head,'struct saturn_cd_hle_device')
    head=head.replace(device,device[:-1]+'\n'+'\n'.join(declarations)+'\n}',1)
    return '#include <algorithm>\n'+head,functions

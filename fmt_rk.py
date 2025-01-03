"""
Original author: Durik256
https://github.com/Durik256/Noesis-Plugins/blob/master/fmt_rk.py

Modified by: eg-lay-atman-bay

The changes made are making texture filename loaded from the .rkm file
as well as applying some properties on the materials found in the .rkm files.
"""

from inc_noesis import *
import csv
import os

def registerNoesisTypes():
    handle = noesis.register("My Little Pony Gameloft", ".rk") # and Ice Age Adventures  
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadModel(handle, noepyLoadModel)
    
    noesis.logPopup()
    return 1
    
def noepyCheckType(data):
    if data[:8] != b'RKFORMAT':
        return 0
    return 1

def split_name_num(name):
    head = name.rstrip('0123456789#')
    tail = name[len(head):]
    return head, tail

def increase_name_num(name):
    head, tail = split_name_num(name)
    number = 0

    if tail:
        number = int(tail)
        number += 1
        return '{head}{number:0{length}d}'.format(
            head = head,
            number = number,
            length = len(tail),
        )
    else:
        return name
    
def noepyLoadModel(data, mdlList):
    bitstream = NoeBitStream(data)
    ctx = rapi.rpgCreateContext()
    bitstream.seek(80)
    
    header = {}
    """
    1  = submesh_inf
    2  = texture
    3  = vert
    4  = face
    6  = transform?
    7  = bones
    13 = attrb
    16 = submesh_name
    17 = weight
    """
    #h = bs.read('68I')

    for x in range(17):
        i = bitstream.read('4I')
        header[i[0]] = i[1:]
    
    bitstream.seek(header[2][0])
    materials, textures = [], []
    for x in range(header[2][1]):
        texture_name = string(bitstream, header[2][2] // header[2][1])
        # if texture_name == '':
        #     texture_name = increase_name_num(materials[-1].name)
        material, texture = loadMaterial(texture_name)
        if material is None:
            materials.append(materials[-1])
        else:
            materials.append(material)
        if texture is None:
            textures.append(textures[-1])
        else:
            textures.append(texture)
    
    #attr - (type,ofs,size)
    bitstream.seek(header[13][0])
    uv_offset, uv_data_type = -1, -1
    for x in range(header[13][1]):
        i = bitstream.read('H2B')
        if i[0] == 1030:
            uv_offset, uv_data_type = i[1], noesis.RPGEODATA_USHORT
            rapi.rpgSetUVScaleBias(NoeVec3([2]*3), None)
        elif i[0] == 1026:
            uv_offset, uv_data_type = i[1], noesis.RPGEODATA_FLOAT
            rapi.rpgSetUVScaleBias(None, None)
    
    submesh_names = []
    
    bitstream.seek(header[16][0])
    for x in range(header[16][1]):
        name = string(bitstream)
        submesh_names.append([name])
        print(name)
    
    bitstream.seek(header[1][0])
    for x in range(header[1][1]):
        #0-numTri,1-ofsIndcs;2-matID;3-unk
        inf = bitstream.read('4I')
        submesh_names[x].append(inf)
        print('inf:',inf)
        
    
    bitstream.seek(header[3][0])
    stride = header[3][2]//header[3][1]
    position_buffer = bitstream.read(header[3][2])
    #rapi.rpgSetMaterial(mList[0].name)
    rapi.rpgBindPositionBuffer(position_buffer, noesis.RPGEODATA_FLOAT, stride)
    #print('uo:',uo)
    if uv_offset != -1:
        rapi.rpgBindUV1BufferOfs(position_buffer, uv_data_type, stride, uv_offset)

    bones = []
    if header[7][1]:
        bitstream.seek(header[7][0])
        for x in range(header[7][1]):
            parent = bitstream.readInt()
            index = bitstream.readInt()
            child = bitstream.readInt()
            matrix = NoeMat44.fromBytes(bitstream.read(64)).toMat43()
            name = string(bitstream)
            bones.append(NoeBone(index, name, matrix, None, parent))
            
        bitstream.seek(header[17][0])
        index_buffer = bitstream.read(header[17][2])
        stride = header[17][2]//header[17][1]
        rapi.rpgBindBoneIndexBuffer(index_buffer, noesis.RPGEODATA_UBYTE, stride, 2)
        rapi.rpgBindBoneWeightBufferOfs(index_buffer, noesis.RPGEODATA_USHORT, stride, 4, 2)
        
    bitstream.seek(header[4][0])
    #ibuf = bs.read(h[4][2])
    #print('h:', h)
    #print('vnum:', h[3][2], 'inum:', h[4][1], 'isize:', h[4][2])
    index_format, index_stride = noesis.RPGEODATA_USHORT, 2
    if header[3][1] > 65535:
        index_format, index_stride = noesis.RPGEODATA_UINT, 4
    
    #rapi.rpgCommitTriangles(ibuf, ifmt, h[4][1], noesis.RPGEO_TRIANGLE)
    for x in submesh_names:
        print(x)
        rapi.rpgSetName(x[0])
        rapi.rpgSetMaterial(materials[x[1][2]].name)
        ibuf = bitstream.read(x[1][0]*3*index_stride)
        rapi.rpgCommitTriangles(ibuf, index_format, x[1][0]*3, noesis.RPGEO_TRIANGLE)
    
    rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)#delete for Ice Age
    model = rapi.rpgConstructModel()  
    model.setModelMaterials(NoeModelMaterials(textures, materials))
    model.setBones(bones)
    mdlList.append(model)
    rapi.setPreviewOption("setAngOfs", "0 90 -90")#delete for Ice Age
    return 1
    
def string(bs, length = 64):
    return bs.read(length).split(b'\x00')[0].decode('ascii', errors='ignore')

def parse_rkm(filename):
    with open(filename, 'r', newline = '') as file:
        data = [row for row in csv.reader(file, delimiter='=') if len(row)]
    return dict(data)

def loadMaterial(material_name):
    filename = rapi.getDirForFilePath(rapi.getInputName())+material_name+'.rkm'

    blend_modes = {
        'none': ('GL_ZERO', 'GL_ZERO'),
        'alpha': ('GL_SRC_ALPHA_SATURATE', 'GL_DST_ALPHA_SATURATE'),
        'add': ('GL_FUNC_ADD','GL_FUNC_ADD'),
    }
    
    print('material', repr(material_name))
    print('filename', filename)
    
    if material_name == '' or not os.path.exists(filename):
        return None, None
    
    rkm = parse_rkm(filename)
    texture_name = rkm.get('DiffuseTexture')
    
    material = NoeMaterial(material_name, texture_name or material_name)
    blend_mode = blend_modes.get(rkm.get('BlendMode', 'none'))
    if blend_mode is not None:
        material.setBlendMode(blend_mode[0], blend_mode[1])

    texture = None
    
    print('texture:', texture_name)
    print('rkm:', rkm)

    
    texture = load_texture(
        texture_name,
        'png' if int(rkm.get('NoCompress', 0)) == 1 else 'pvr',
    )
    
    if int(rkm.get('Cull', 0)) == 0:
        material.flags |= noesis.NMATFLAG_TWOSIDED
    
    if texture is not None:
        clamp = rkm.get('ClampMode')
        CLAMP_MODES = {
            'RK_REPEAT': noesis.NTEXFLAG_WRAP_T_REPEAT,
        }
        
        if clamp in CLAMP_MODES:
            texture.flags |= CLAMP_MODES[clamp]
    
    return material, texture
    

def load_texture(texture_name, format = 'pvr'):
    print('loading', texture_name)
    try:
        if format == 'pvr':
            data = rapi.loadIntoByteArray(rapi.getDirForFilePath(rapi.getInputName())+texture_name+'.pvr')
            header = struct.unpack('8I', data[:32])
            w, h, format = header[6], header[7], header[2]

            if format == 34:
                data = rapi.imageDecodeASTC(data[67:], 8, 8, 1, w, h, 1)
            elif format == 6:
                data = rapi.imageDecodeETC(data[52:], w, h, 'RGB')
            else:
                return
            
            return NoeTexture(texture_name, w, h, data, noesis.NOESISTEX_RGBA32)
        else:
            return rapi.loadImageRGBA(texture_name + '.' + format)
    except:
        print('error load tx!')

import math
import numpy as np
import vtk
import pydicom

def scale_mat_from_to(mat, from_min=None, from_max=None, to_min=0, to_max=255, dtype=np.uint8):
    if from_min is None:
        from_min = np.min(mat)
    if from_max is None:
        from_max = np.max(mat)
    return np.interp(mat, (from_min, from_max), (to_min, to_max)).astype(dtype)


def crop(array):
    xmin = ymin = zmin = np.max(array.shape)
    xmax = ymax = zmax = 0
    for z in range(array.shape[0]):
        for y in range(array.shape[1]):
            for x in range(array.shape[2]):
                if array[z,y,x]:
                    if x < xmin:
                        xmin = x
                    elif x > xmax:
                        xmax = x
                    if y < ymin:
                        ymin = y
                    elif y > ymax:
                        ymax = y
                    if z < zmin:
                        zmin = z
                    elif z > zmax:
                        zmax = z
    return array[zmin:zmax,ymin:ymax,xmin:xmax]


def turn_upside_down(array):
    flipped = np.rot90(array, 2, (1, 2))
    return np.rot90(flipped, 2, (0, 2))


def multi_tiff_to_numpy(filename):
    import pytiff
    with pytiff.Tiff(filename) as handle:
        arr = np.ndarray(shape=(handle.number_of_pages, handle.shape[0], handle.shape[1]), dtype=handle.dtype)
        for i, page in enumerate(handle.pages):
            arr[i] = page
        return arr


def dicom_to_numpy(filename: str):
    return pydicom.dcmread(filename).pixel_array

def rot_mat_to_euler(R, deg=True):
    R = np.array(R)
    alpha_x = np.arctan2(R[2, 1], R[2, 2])
    alpha_y = np.arctan2(-R[2, 0], np.sqrt(R[1, 2] ** 2 + R[2, 2] ** 2))
    alpha_z = np.arctan2(R[0, 1], R[0, 0])
    if deg:
        alpha_x = np.rad2deg(alpha_x)
        alpha_y = np.rad2deg(alpha_y)
        alpha_z = np.rad2deg(alpha_z)
    return alpha_x, alpha_y, alpha_z


def get_rotation(rot_angle_x, rot_angle_y, rot_angle_z):
    def s(x):
        return math.sin(math.radians(x))

    def c(x):
        return math.cos(math.radians(x))
        # try lambda expressions....
        # c = lambda x:math.cos(math.radians(x))

    ##Rx
    rX = np.matrix(np.zeros(shape=(4, 4)), dtype=np.float64)
    rX[0, 0] = 1.0
    rX[1, 1] = c(rot_angle_x)
    rX[1, 2] = -s(rot_angle_x)
    rX[2, 1] = s(rot_angle_x)
    rX[2, 2] = c(rot_angle_x)
    rX[3, 3] = 1.0

    ##Ry
    rY = np.matrix(np.zeros(shape=(4, 4)), dtype=np.float64)
    rY[1, 1] = 1.0
    rY[0, 0] = c(rot_angle_y)
    rY[0, 2] = s(rot_angle_y)
    rY[2, 0] = -s(rot_angle_y)
    rY[2, 2] = c(rot_angle_y)
    rY[3, 3] = 1.0

    ##Rz
    rZ = np.matrix(np.zeros(shape=(4, 4)), dtype=np.float64)
    rZ[0, 0] = c(rot_angle_z)
    rZ[0, 1] = -s(rot_angle_z)
    rZ[1, 0] = s(rot_angle_z)
    rZ[1, 1] = c(rot_angle_z)
    rZ[2, 2] = 1.0
    rZ[3, 3] = 1.0

    return rZ * rY * rX


def get_Rt(rotation):
    t_ax = rotation[1]
    t_cor = rotation[2]
    t_sag = rotation[0]

    R_ax = rotation[5]
    R_cor = rotation[3]
    R_sag = rotation[4]

    ###need to make some further thinking about x,y,z settings
    rotMat = get_rotation(R_ax, R_cor, R_sag)
    rotMat[0:3, 3] = np.matrix([t_ax, t_cor, t_sag]).T
    return rotMat


def get_Rt_for_file(rotation):
    # we need different motion mapping, because the head is rotated by 90 degree
    # as otherwise we would see the head from the bottom...thus some things change
    t_ax = rotation[0]
    t_coronal = rotation[1]
    t_sagittal = rotation[2]

    R_sag = rotation[5]
    R_cor = rotation[4]
    R_ax = rotation[3]
    ####w.r.t. the code it is supposed to be:
    # 3 -> axial
    # 4 -> coronal
    # 5 -> sagittal
    ###need to make some further thinking about x,y,z settings
    ##get_rotation(x_axis, y_axis, z_axis)
    rotMat = get_rotation(R_sag, R_cor, -R_ax)
    # rotMat[0:3, 3] = np.matrix([t_ax, t_cor, t_sag]).T
    rotMat[0:3, 3] = np.matrix([-t_coronal, t_ax, t_sagittal]).T
    return rotMat


def GetVTKMatrix(mat):
    matrix = vtk.vtkMatrix4x4()
    for i in range(0, 4):
        for j in range(0, 4):
            matrix.SetElement(i, j, mat[i, j])
    return matrix


def add_motion_to_pMat(pMat_list, motion_array):
    ###create empty list for 4x4 rotation and translation matrix (affine)
    rt_list = []
    ###create empty list for motion corrupted projection matrices
    motion_corrupted_pmat = []
    ## iterate over array --> note that we need to iterate over the projection matrices
    ## because it might be that there are more motions then projection matrices
    ## as currently the protitype is defined, such that the two planes could have
    ## different amounts of projections...i think that actually the two projection planes
    ## should actually aquire the same amount of projections
    for i in range(len(pMat_list)):
        ## append Rotation matrix to list of rotation matrices
        rt_list.append(get_Rt_for_file(motion_array[i]))
        ## multiply P*R to obtain motion in respective view
        motion_corrupted_pmat.append(np.matrix(pMat_list[i]) * rt_list[-1])
    return [motion_corrupted_pmat, rt_list]

import os
from typing import Optional
from loguru import logger


def activate_virtual_framebuffer():
    """
    Activates a virtual (headless) framebuffer for rendering 3D
    scenes via VTK.

    Most critically, this function is useful when this code is being run
    in a Dockerized notebook, or over a server without X forwarding.

    * Requires the following packages:
      * `sudo apt-get install libgl1-mesa-dev xvfb`
    """

    import subprocess
    import vtk

    vtk.OFFSCREEN = True
    os.environ["DISPLAY"] = ":99.0"

    commands = [
        "Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &",
        "sleep 3",
        'exec "$@"',
    ]

    for command in commands:
        subprocess.call(command, shell=True)


if os.path.isdir("/app"):
    print("Activating virtual framebuffer")
    activate_virtual_framebuffer()

import vtk  # noqa: E402


def render(
    filenames: list[str],
    positions: list[tuple[float, float, float]],
    colors: list[tuple[float, float, float]],
    camera_positions: list[
        tuple[tuple[float, float, float], tuple[float, float, float], str]
    ],
    output_path: str,
    prefix: Optional[str] = None,
    transparent_background: bool = False,
):
    # Create a rendering window and renderer
    ren = vtk.vtkRenderer()
    renWin = vtk.vtkRenderWindow()
    renWin.SetSize(800, 800)
    renWin.SetOffScreenRendering(1)
    renWin.AddRenderer(ren)
    if transparent_background:
        renWin.SetAlphaBitPlanes(1)

    for filename, position, color in zip(filenames, positions, colors):
        try:
            polydata = loadStl(filename)
        except Exception as e:
            logger.error(f"Error loading STL file {filename}: {e}")
            raise e
        actor = polyDataToActor(polydata, color)
        actor.SetPosition(*position)
        # ren.SetLayer(1)
        ren.AddActor(actor)

    light = vtk.vtkLight()
    light.SetFocalPoint(0, 0, 0)
    light.SetPosition(1, 1, 2)
    light.SetIntensity(0.5)
    ren.AddLight(light)

    light2 = vtk.vtkLight()
    light2.SetFocalPoint(0, 0, 0)
    light2.SetPosition(-1, 1, 2)
    light2.SetIntensity(0.5)
    ren.AddLight(light2)

    light3 = vtk.vtkLight()
    light3.SetFocalPoint(0, 0, 0)
    light3.SetPosition(0.5, 0.5, 0)
    light3.SetIntensity(0.5)
    ren.AddLight(light3)

    if transparent_background:
        ren.SetBackground(0.5, 0.5, 0.5)
        ren.SetBackgroundAlpha(0.0)
        ren.SetUseDepthPeeling(1)
        ren.SetOcclusionRatio(0.1)
    else:
        ren.SetBackground(255, 255, 255)

    renWin.Render()

    camera = ren.GetActiveCamera()
    camera_dist_to_origin = camera.GetDistance() * 1.1
    camera.SetClippingRange(0.1, camera_dist_to_origin * 2)

    camera.Zoom(1.1)

    for position in camera_positions:
        (vt_x, vt_y, vt_z), (x, y, z), pos_name = position
        x = x * camera_dist_to_origin
        y = y * camera_dist_to_origin
        z = z * camera_dist_to_origin
        camera.SetPosition(x, y, z)
        camera.SetViewUp(vt_x, vt_y, vt_z)
        renWin.Render()

        windowToImageFilter = vtk.vtkWindowToImageFilter()
        windowToImageFilter.SetInput(renWin)
        if transparent_background:
            windowToImageFilter.SetInputBufferTypeToRGBA()
        windowToImageFilter.Update()

        writer = None
        filename = None
        if transparent_background:
            writer = vtk.vtkPNGWriter()
        else:
            writer = vtk.vtkJPEGWriter()

        if len(camera_positions) == 1:
            filename = output_path
        if transparent_background and len(camera_positions) > 1:
            filename = f"{output_path}/{prefix + '_' if prefix else ''}{pos_name}.png"
        if not transparent_background and len(camera_positions) > 1:
            filename = f"{output_path}/{prefix + '_' if prefix else ''}{pos_name}.jpg"

        writer.SetFileName(filename)

        writer.SetInputConnection(windowToImageFilter.GetOutputPort())
        writer.Write()

    # Clean up
    renWin.Finalize()
    ren.RemoveAllViewProps()


def loadStl(fname):
    """Load the given STL file, and return a vtkPolyData object for it."""
    if not os.path.exists(fname):
        raise FileNotFoundError(f"File {fname} not found")

    reader = vtk.vtkSTLReader()
    reader.SetFileName(fname)
    reader.Update()
    polydata = reader.GetOutput()
    return polydata


def polyDataToActor(polydata, color=(0.5, 0.5, 1.0)):
    """Wrap the provided vtkPolyData object in a mapper and an actor, returning
    the actor."""
    mapper = vtk.vtkPolyDataMapper()
    if vtk.VTK_MAJOR_VERSION <= 5:
        mapper.SetInput(polydata)
    else:
        mapper.SetInputData(polydata)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    return actor

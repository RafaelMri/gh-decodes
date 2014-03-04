from .. import *
from ..core import *
from ..core import dc_color, dc_base, dc_vec, dc_point, dc_cs, dc_line, dc_mesh, dc_pgon, dc_xform, dc_intersection
from .rhino_in import *
if VERBOSE_FS: print "dynamo_in loaded"

#import Rhino.Geometry as ds
#import System.Drawing.Color

import clr, collections

clr.AddReference('ProtoGeometry')
import Autodesk.DesignScript.Geometry as ds

#TODO: figure out how to hack the code completion thingo to display decodes geometry after gh geom has been translated



class DynamoIn():
    """innie for pulling stuff from dynamo"""
    primitive_types = ["bool", "int", "float", "str"]
    structure_types = ["classobj", "instance", "function", "class"]
    friendly_types = ["DHr"]
    
    def __init__(self):
        pass
        
    @staticmethod
    #def get(dyn_in_str, dyn_in):
    def get(dyn_in):
        # main function for processing incoming data from Dynamo into Decodes geometry
        # incoming may be a sigleton, a list, or a list of lists
        # variable in Dynamo script component will be replaced by whatever is returned here

        if dyn_in is None : return None
        #################################################################################################################
        # THIS WILL HAVE TO WAIT TILL THEY FIX THEIR COMPONENT
        #################################################################################################################
        if type(dyn_in) is list: return [DynamoIn.get(dyn_in_str+"["+str(i)+"]",item) for i, item in enumerate(dyn_in)]
        
        # NO INTERVALS IN DYNAMO/DS
        #if type(dyn_in) is ds.Interval: return Interval(dyn_in.T0,dyn_in.T1)

        if type(dyn_in) is ds.Rectangle :  dyn_in = ds.PolyCurve.ByPoints(ds.dyn_in.Corners, True)

        if type(dyn_in) is ds.Vector: return from_dynvec(dyn_in)
        elif type(dyn_in)is ds.Point: return from_dynpt(dyn_in)
        elif type(dyn_in)is ds.Vertex: return from_dynpt(dyn_in.PointGeometry)
        elif type(dyn_in)is ds.Plane : 
            return Plane(from_dynpt(dyn_in.Origin), from_dynvec(dyn_in.Normal))
        elif type(dyn_in)is ds.CoordinateSystem : 
            return from_dyncs(dyn_in)
        elif type(dyn_in) is ds.Line : 
            return Segment(from_dynpt(dyn_in.StartPoint), from_dynpt(dyn_in.EndPoint))
        elif type(dyn_in) is ds.Edge : 
            return Segment(from_dynpt(dyn_in.StartVertex), from_dynpt(dyn_in.EndVertex))
        # No idea how colors are defined in the new protgeometry.....
        """
        elif type(dyn_in) is System.Drawing.Color : 
            return Color(float(dyn_in.R)/255,float(dyn_in.G)/255,float(dyn_in.B)/255)"""

        elif type(dyn_in)is ds.Circle :
            pln = Plane(from_dynpt(dyn_in.CenterPoint), from_dynvec(dyn_in.Normal))
            return Circle(pln,dyn_in.Radius)
        elif type(dyn_in)is ds.Arc :
            x_axis = Vec(from_dynpt(dyn_in.CenterPoint),from_dynpt(dyn_in.StartPoint))
            y_axis = from_dynvec(dyn_in.Normal).cross(x_axis)
            cs = CS( from_dynpt(dyn_in.CenterPoint), x_axis, y_axis )
            swp_ang = abs(dyn_in.SweepAngle * 0.0174532925)
            return Arc(cs,dyn_in.Radius,swp_ang)
        elif type(dyn_in) is ds.PolyCurve: 
            return from_dspolyline(dyn_in)
        elif type(dyn_in) is ds.Polygon:
            return from_dspolygon(dyn_in)
        elif type(dyn_in) is ds.NurbsCurve : 
            #Approximates a nurbscrv into a PLine
            return from_nurbscurve(dyn_in)
        elif type(dyn_in) is ds.Ellipse : 
            #Approximates an ellipse into a PLine
            #TODO mathematical description of ellipse to return decodes curve
            return from_nurbscurve(dyn_in)
        elif type(dyn_in) is ds.Mesh : 
            verts = [from_dynpt(pt) for pt in dyn_in.VertexPositions]
            faces = []
            for face in dyn_in.FaceIndices:
                faces.append(face.A, face.B, face.C, face.D)
            return Mesh(verts,faces)

        elif any(p in str(type(dyn_in)) for p in DynamoIn.primitive_types) : return dyn_in
        elif any(p in str(type(dyn_in)) for p in DynamoIn.friendly_types) : return dyn_in
        elif any(p in str(type(dyn_in)) for p in DynamoIn.structure_types) : return dyn_in
        else :
            print "UNKNOWN TYPE: "+str(type(dyn_in))+" is an "+ str(type(dyn_in))
            return dyn_in
            #print inspect.getmro(dyn_in.__class__)
            #if issubclass(dyn_in.__class__, ds.GeometryBase ) : print "this is geometry"
            #print dyn_incoming.TypeHint
            #print dyn_incoming.Description


def from_dynvec(dyn_vec):
    return Vec(dyn_vec.X,dyn_vec.Y,dyn_vec.Z)

def from_dynpt(dyn_pt):
    return Point(dyn_pt.X,dyn_pt.Y,dyn_pt.Z)

def from_dyncs(dyn_cs):
        cpt = from_dynpt(dyn_cs.Origin)
        x_axis = from_dynvec(dyn_cs.XAxis)
        y_axis = from_dynvec(dyn_cs.YAxis)
        return CS(cpt,x_axis,y_axis)

def from_polycurve(dyn_polycurve):
    crvs = dyn_polycurve.Curves()
    verts = [from_dynpt(crv.StartPoint) for crv in crvs]
    verts.append(from_dynpt(crvs[len(crvs)-1].EndPoint))
    return verts  
        
def from_dspolyline(dyn_polyline):
    if not dyn_polyline.IsClosed : 
        w_verts = from_polycurve(dyn_polyline)
        return PLine(w_verts)
    else:
        if not dyn_polyline.IsPlanar() : raise GeometricError("Cannot import non-planar polylines as polygons.  Did you give me degenerate geometry?")
        cs = from_dyncs(dyn_polyline.ContextCoordinateSystem)
        w_verts = from_polycurve(dyn_polyline)
        verts = [ Vec(pt*cs.ixform) for pt in w_verts ]
        if (verts[0]==verts[-1]) : del verts[-1] #remove last vert if a duplicate
        return PGon(verts,cs)
    
def from_dspolygon(dyn_polygon):
    cs = from_dyncs(dyn_polygon.ContextCoordinateSystem)
    w_verts = [from_dynpt(pt) for pt in dyn_polygon.Points]
    verts = [ Vec(pt*cs.ixform) for pt in w_verts ]
    if (verts[0]==verts[-1]) : del verts[-1] #remove last vert if a duplicate
    return PGon(verts,cs)
    
def from_nurbscurve(dyn_nurbscurve):
    rng = Interval().divide(100, True)
    verts = [from_dynpt(dyn_nurbscurve.PointAtParameter(i)) for i in rng]
    return PLine(verts)
    
def from_dstransform(rh_xf):
    xf = Xform()
    xf.m00, xf.m01, xf.m02, xf.m03 = rh_xf.M00, rh_xf.M01, rh_xf.M02, rh_xf.M03
    xf.m10, xf.m11, xf.m12, xf.m13 = rh_xf.M10, rh_xf.M11, rh_xf.M12, rh_xf.M13
    xf.m20, xf.m21, xf.m22, xf.m23 = rh_xf.M20, rh_xf.M21, rh_xf.M22, rh_xf.M23
    xf.m30, xf.m31, xf.m32, xf.m33 = rh_xf.M30, rh_xf.M31, rh_xf.M32, rh_xf.M33
    return xf

'''
for reference: the following code is injected before and after a user's script in grasshopper components
## -- BEGIN DECODES HEADER -- ##
import decodes as dc
from decodes.core import *
from decodes.io.dyn_in import *
from decodes.io.gh_out import *
exec(io.dyn_in.component_header_code)
exec(io.gh_out.component_header_code)
## -- END DECODES HEADER -- ##

## -- BEGIN DECODES FOOTER -- ##
exec(io.dyn_in.component_footer_code)
exec(io.gh_out.component_footer_code)
## -- END DECODES FOOTER -- ##
'''
        
#TODO: make this into a proper innie instead
component_header_code = """
inputs = ghenv.Component.Params.Input
import Rhino.Geometry as rg
import System.Drawing.Color
for input in inputs : 
        dyn_in_str = input.Name
        vars()[dyn_in_str] = GrasshopperIn.get(dyn_in_str, eval(dyn_in_str))
"""

component_footer_code = ""
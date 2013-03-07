from pyspades.server import block_action, grenade_packet, create_player
from pyspades.common import coordinates, Vertex3
from pyspades.constants import *
from pyspades.collision import distance_3d_vector
from twisted.internet import reactor
from pyspades.world import Mortar


import commands

@commands.alias('m')

def mortar(connection):
    return connection.mortar()

    
commands.add(mortar)
def apply_script(protocol, connection, config):
    def try_add_node(map, x, y, z, list):
        if x < 0 or x >= 512 or y < 0 or y >= 512 or z < 0 or z >= 62:
            return
        if map.get_solid(x, y, z):
            return
        list.append((x, y, z))
        
        
    class DirtGrenadeConnection(connection):
        def mortar( self ):
            if self.name is None:
                return
            fuse = 6
            grenade_packet.value = fuse
            grenade_packet.player_id = self.player_id
            grenade_packet.position = (self.world_object.position.x,self.world_object.position.y,self.world_object.position.z)
            grenade_packet.velocity = (self.world_object.orientation.x, self.world_object.orientation.y, self.world_object.orientation.z)
            #self.protocol.send_contained(grenade_packet)
           
            position = Vertex3(self.world_object.position.x,self.world_object.position.y,self.world_object.position.z)
            velocity = Vertex3(self.world_object.orientation.x, self.world_object.orientation.y, self.world_object.orientation.z)
            airstrike = self.protocol.world.create_object(Mortar, fuse, 
                position, None, 
                velocity, self.mortar_exploded, 20.0)
            position+=velocity*3;
            airstrike2 = self.protocol.world.create_object(Mortar, 0.0, 
                position, None, 
                velocity, self.mortar_exploded, 0.0)
            connection.grenade_exploded(self, airstrike2)

        def mortar_exploded(self, grenade):
            if self.name is None:
                return
            fuse = 0
            grenade_packet.value = fuse
            grenade_packet.player_id = self.player_id
            grenade_packet.position = (grenade.position.x,grenade.position.y,grenade.position.z)
            grenade_packet.velocity = (grenade.acceleration.x, grenade.acceleration.y, grenade.acceleration.z)
            self.protocol.send_contained(grenade_packet)

            position = grenade.position
            connection.grenade_exploded(self, grenade)
            self.send_chat("Threw")
            if grenade.explosive > 0:
                reactor.callLater( 0.01, self.remove_sphere,grenade.position.x,grenade.position.y,grenade.position.z-1, 7 )
                self.protocol.update_entities()
            
        def fval(self,x,y,z,r):
            return x*x + y*y + z*z - r*r
        
        def make_crater( self, sphere, mode ):
            for blk in sphere:
                
                block_action.x = ( blk[0] )
                block_action.y = ( blk[1]  )
                block_action.z = ( blk[2]  )
                block_action.value = mode
                block_action.player_id = self.player_id
                self.protocol.send_contained( block_action )
                if mode == 0:
                    self.protocol.map.remove_point( block_action.x,block_action.y,block_action.z )

                self.protocol.update_entities()    
                
        def remove_sphere( self , x,y,z, dia ):
            sphere = set()
            radius = dia/2;
            midX = midY = midZ = (dia-1)/2;
            for nade_x in xrange ( 0, dia, 1 ) :
                for nade_y in xrange( 0,  dia, 1):
                    for nade_z in xrange(0, dia, 1):
                        
                        bx = (  x + nade_x-midX )
                        by = (  y + nade_y-midY )
                        bz = (  z + nade_z-midZ )
                        if bx>= 0 and bx <= 512 and by >= 0 and by <= 512 and bz >= 0 and bz < 63:
                            fval = self.fval( nade_x-midX, nade_y-midY, nade_z-midZ, radius)
                            # remove all blocks on the outside of the sphere 1 square thick
                            # include all ground plane ones to destroy land mass ;)
                            if( ( fval >= -(dia) and fval <= 0 ) or ( bz == 61 and fval <= 0 ) ):
    
                                block_action.value = 1
                                block_action.player_id = self.player_id
                                        
                                if self.protocol.map.get_solid( bx, by, bz ) or self.protocol.map.get_point( bx, by, bz )[0] == True:
                                    #self.protocol.send_contained( block_action )
                                    sphere.add( ( bx,by,bz ) )

                            if self.fval( nade_x-midX, nade_y-midY, nade_z-midZ, radius) <= 0:
                                #self.protocol.send_contained( block_action )
                                self.protocol.map.remove_point( bx,by,bz  )
                                #self.protocol.map.set_point( bx,by,bz+2, (255,0,0,0) )
                                self.protocol.update_entities()
                
            self.make_crater( sphere, 1 )
            
            
                # self.protocol.map.set_point_unsafe(block_action.x, block_action.y, 63, 255)
            return sphere
    return protocol, DirtGrenadeConnection

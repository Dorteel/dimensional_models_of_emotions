(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    carton1 - carton
    carton2 - carton
    cabinet1 - cabinet
    bottle_of_lotion1 - bottle_of_lotion
    bottle_of_detergent1 - bottle_of_detergent
    picture_frame1 - picture_frame
    picture_frame2 - picture_frame
    picture_frame3 - picture_frame
    notebook1 - notebook
    notebook2 - notebook
    notebook3 - notebook
    painting1 - painting
    painting2 - painting
    plastic_art1 - plastic_art
    lampshade1 - lampshade
    lampshade2 - lampshade
    globe1 - globe
    console_table1 - console_table
    floor1 - floor
    living_room - location
  )
  (:init
    (on_top carton1 floor1)
    (on_top carton2 floor1)
    (in bottle_of_lotion1 carton1)
    (in bottle_of_detergent1 carton1)
    (in picture_frame1 carton1)
    (in picture_frame2 carton1)
    (in picture_frame3 carton1)
    (in notebook1 carton1)
    (in notebook2 carton1)
    (in notebook3 carton1)
    (in painting1 carton2)
    (in painting2 carton2)
    (in plastic_art1 carton2)
    (in lampshade1 carton2)
    (in lampshade2 carton2)
    (in globe1 carton2)
    (at floor1 living_room)
    (at console_table1 living_room)
    (at cabinet1 living_room)
    (at carton1 living_room)
    (at carton2 living_room)
    (at bottle_of_lotion1 living_room)
    (at bottle_of_detergent1 living_room)
    (at picture_frame1 living_room)
    (at picture_frame2 living_room)
    (at picture_frame3 living_room)
    (at notebook1 living_room)
    (at notebook2 living_room)
    (at notebook3 living_room)
    (at painting1 living_room)
    (at painting2 living_room)
    (at plastic_art1 living_room)
    (at lampshade1 living_room)
    (at lampshade2 living_room)
    (at globe1 living_room)
    (at robot1 living_room)
    (robot_free robot1)
  )
  (:goal
  (and
    (on_top notebook1 console_table1)
    (on_top notebook2 console_table1)
    (on_top notebook3 console_table1)
    (on_top picture_frame1 console_table1)
    (on_top picture_frame2 console_table1)
    (on_top picture_frame3 console_table1)
    (on_top bottle_of_lotion1 console_table1)
    (on_top plastic_art1 console_table1)
    (on_top globe1 console_table1)

    (on_top painting1 cabinet1)
    (on_top painting2 cabinet1)
    (on_top bottle_of_detergent1 cabinet1)
    (on_top lampshade1 cabinet1)
    (on_top lampshade2 cabinet1)

    (next_to carton1 console_table1)
    (next_to carton2 console_table1)
  )
)
)

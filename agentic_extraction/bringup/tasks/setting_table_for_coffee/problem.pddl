(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    pitcher1 - pitcher
    countertop1 - countertop
    box_of_cream1 - box_of_cream
    cabinet1 - cabinet
    napkin1 - napkin
    napkin2 - napkin
    breakfast_table1 - breakfast_table
    bowl1 - bowl
    teaspoon1 - teaspoon
    teaspoon2 - teaspoon
    electric_refrigerator1 - electric_refrigerator
    floor1 - floor
    kitchen - location
    dining_room - location
  )
  (:init
    (on_top pitcher1 countertop1)
    (in box_of_cream1 electric_refrigerator1)
    (on_top napkin1 breakfast_table1)
    (on_top napkin2 breakfast_table1)
    (in teaspoon1 cabinet1)
    (in teaspoon2 cabinet1)
    (on_top bowl1 countertop1)
    (at breakfast_table1 dining_room)
    (at cabinet1 kitchen)
    (at countertop1 kitchen)
    (at electric_refrigerator1 kitchen)
    (at pitcher1 kitchen)
    (at box_of_cream1 kitchen)
    (at napkin1 dining_room)
    (at napkin2 dining_room)
    (at teaspoon1 kitchen)
    (at teaspoon2 kitchen)
    (at bowl1 kitchen)
    (at robot1 kitchen)
    (robot_free robot1)
  )
  (:goal
  (and
    (at box_of_cream1 dining_room)
    (at teaspoon1 dining_room)
    (at teaspoon2 dining_room)
    (at bowl1 dining_room)
    (at pitcher1 kitchen)
    (at napkin1 dining_room)
    (at napkin2 dining_room)
    (on_top napkin1 breakfast_table1)
    (on_top napkin2 breakfast_table1)
  )
)
)

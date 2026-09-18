(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    cupcake1 - cupcake
    cupcake2 - cupcake
    plate1 - plate
    plate2 - plate
    tablefork1 - tablefork
    tablefork2 - tablefork
    table_knife1 - table_knife
    table_knife2 - table_knife
    breakfast_table1 - breakfast_table
    cabinet1 - cabinet
    electric_refrigerator1 - electric_refrigerator
    sink1 - sink
    kitchen - location
    dining_room - location
  )
  (:init
    (at robot1 kitchen)
    (at breakfast_table1 dining_room)
    (at cabinet1 kitchen)
    (at electric_refrigerator1 kitchen)
    (at sink1 kitchen)
    (at cupcake1 kitchen)
    (at cupcake2 kitchen)
    (at plate1 kitchen)
    (at plate2 kitchen)
    (at tablefork1 kitchen)
    (at tablefork2 kitchen)
    (at table_knife1 kitchen)
    (at table_knife2 kitchen)
    (in cupcake1 electric_refrigerator1)
    (in cupcake2 electric_refrigerator1)
    (in plate1 cabinet1)
    (in plate2 cabinet1)
    (on_top tablefork1 sink1)
    (on_top tablefork2 sink1)
    (on_top table_knife1 sink1)
    (on_top table_knife2 sink1)
    (robot_free robot1)
  )
  (:goal
  (and
    (on_top plate1 breakfast_table1)
    (on_top cupcake1 plate1)
    (next_to tablefork1 plate1)
    (next_to table_knife1 plate1)

    (on_top plate2 breakfast_table1)
    (on_top cupcake2 plate2)
    (next_to tablefork2 plate2)
    (next_to table_knife2 plate2)
  )
)
)

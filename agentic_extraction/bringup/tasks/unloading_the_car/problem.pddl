(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    car1 - car
    briefcase1 - briefcase
    satchel1 - satchel
    sofa1 - sofa
    garage - location
    living_room - location
  )
  (:init
    (in briefcase1 car1)
    (in satchel1 car1)
    (at car1 garage)
    (at sofa1 living_room)
    (at briefcase1 garage)
    (at satchel1 garage)
    (at robot1 garage)
    (robot_free robot1)
  )
  (:goal
  (and
    (at briefcase1 living_room)
    (next_to briefcase1 sofa1)
    (at satchel1 living_room)
    (next_to satchel1 sofa1)
  )
)
)

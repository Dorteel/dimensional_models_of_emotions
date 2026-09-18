(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    plate1 - plate
    bowl1 - bowl
    apple1 - apple
    pear1 - pear
    orange1 - orange
    banana1 - banana
    table1 - table
    home - location
    wp2 - location
    wp3 - location
    wp4 - location
    wp5 - location
    wp6 - location
    wp7 - location
    wp8 - location
  )
  (:init
    (at robot1 home)
    (at table1 wp2)
    (at plate1 wp3)
    (at bowl1 wp4)
    (at apple1 wp5)
    (at pear1 wp6)
    (at orange1 wp7)
    (at banana1 wp8)
    (robot_free robot1)
  )
  (:goal
  (and
    (on_top banana1 plate1)
    (on_top pear1 plate1)
    (in apple1 bowl1)
    (in orange1 bowl1)
  )
)
)

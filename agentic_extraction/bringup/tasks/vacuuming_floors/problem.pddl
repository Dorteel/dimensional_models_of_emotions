(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    dust1 - dust
    floor1 - floor
    vacuum1 - vacuum
    bedroom - location
  )
  (:init
    (covered floor1 dust1)
    (on_top vacuum1 floor1)
    (at floor1 bedroom)
    (at vacuum1 bedroom)
    (at robot1 bedroom)
    (robot_free robot1)
  )
  (:goal
  (and
    (not (covered floor1 dust1))
  )
)
)

(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    car1 - car
    vacuum1 - vacuum
    dust1 - dust
    floor1 - floor
    garden - location
    garage - location
  )
  (:init
    (covered car1 dust1)
    (on_top vacuum1 floor1)
    (at car1 garden)
    (at floor1 garage)
    (at vacuum1 garage)
    (at robot1 garage)
    (robot_free robot1)
  )
  (:goal
  (and
    (not (covered car1 dust1))
  )
)
)

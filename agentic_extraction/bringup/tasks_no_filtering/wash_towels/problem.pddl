(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    bath_towel1 - bath_towel
    bath_towel2 - bath_towel
    dirt1 - dirt
    washer1 - washer
    clothes_dryer1 - clothes_dryer
    detergent_bottle1 - detergent_bottle
    floor1 - floor
    utility_room - location
  )
  (:init
    (on_top bath_towel2 washer1)
    (on_top bath_towel1 floor1)
    (covered bath_towel1 dirt1)
    (covered bath_towel2 dirt1)
    (on_top detergent_bottle1 floor1)
    (at floor1 utility_room)
    (at clothes_dryer1 utility_room)
    (at washer1 utility_room)
    (at bath_towel1 utility_room)
    (at bath_towel2 utility_room)
    (at detergent_bottle1 utility_room)
    (at robot1 utility_room)
    (robot_free robot1)
  )
  (:goal
  (and
    (not (covered bath_towel1 dirt1))
    (not (covered bath_towel2 dirt1))
  )
)
)

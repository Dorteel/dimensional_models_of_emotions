(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    sour_bread1 - sour_bread
    sack1 - sack
    box_of_corn_flakes1 - box_of_corn_flakes
    cup_of_yogurt1 - cup_of_yogurt
    egg1 - egg
    electric_refrigerator1 - electric_refrigerator
    cabinet1 - cabinet
    floor1 - floor
    kitchen - location
  )
  (:init
    (in sour_bread1 sack1)
    (in box_of_corn_flakes1 sack1)
    (in cup_of_yogurt1 sack1)
    (in egg1 sack1)
    (on_top sack1 floor1)
    (at cabinet1 kitchen)
    (at electric_refrigerator1 kitchen)
    (at sack1 kitchen)
    (at sour_bread1 kitchen)
    (at box_of_corn_flakes1 kitchen)
    (at cup_of_yogurt1 kitchen)
    (at egg1 kitchen)
    (at robot1 kitchen)
    (robot_free robot1)
  )
  (:goal
  (and
    (in sour_bread1 cabinet1)
    (in box_of_corn_flakes1 cabinet1)
    (in cup_of_yogurt1 electric_refrigerator1)
    (in egg1 electric_refrigerator1)
    (not (open cabinet1))
    (not (open electric_refrigerator1))
  )
)
)

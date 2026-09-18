(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    computer1 - computer
    computer2 - computer
    desk1 - desk
    desk2 - desk
    keyboard1 - keyboard
    keyboard2 - keyboard
    mouse1 - mouse
    mouse2 - mouse
    legal_document1 - legal_document
    carton1 - carton
    sheet1 - sheet
    pen1 - pen
    book1 - book
    recycling_bin1 - recycling_bin
    folder1 - folder
    rag1 - rag
    dust1 - dust
    floor1 - floor
    shared_office - location
  )
  (:init
    (on_top computer1 desk1)
    (on_top keyboard1 desk1)
    (on_top mouse1 desk1)
    (on_top computer2 desk2)
    (on_top keyboard2 desk2)
    (on_top mouse2 desk2)
    (on_top legal_document1 desk1)
    (on_top carton1 desk1)
    (on_top sheet1 desk2)
    (on_top pen1 desk1)
    (on_top book1 desk2)
    (on_top recycling_bin1 floor1)
    (on_top folder1 desk2)
    (on_top rag1 floor1)
    (covered desk1 dust1)
    (covered computer1 dust1)
    (covered desk2 dust1)
    (covered computer2 dust1)
    (covered keyboard1 dust1)
    (covered mouse1 dust1)
    (covered keyboard2 dust1)
    (covered mouse2 dust1)
    (at desk1 shared_office)
    (at desk2 shared_office)
    (at floor1 shared_office)
    (at computer1 shared_office)
    (at computer2 shared_office)
    (at keyboard1 shared_office)
    (at keyboard2 shared_office)
    (at mouse1 shared_office)
    (at mouse2 shared_office)
    (at legal_document1 shared_office)
    (at carton1 shared_office)
    (at sheet1 shared_office)
    (at pen1 shared_office)
    (at book1 shared_office)
    (at recycling_bin1 shared_office)
    (at folder1 shared_office)
    (at rag1 shared_office)
    (at robot1 shared_office)
    (robot_free robot1)
  )
  (:goal
  (and
    (not (covered desk1 dust1))
    (not (covered desk2 dust1))
    (not (covered computer1 dust1))
    (not (covered computer2 dust1))
    (not (covered keyboard1 dust1))
    (not (covered keyboard2 dust1))
    (not (covered mouse1 dust1))
    (not (covered mouse2 dust1))
    (in sheet1 carton1)
    (in legal_document1 carton1)
    (in pen1 carton1)
    (in book1 carton1)
    (in folder1 carton1)
    (on_top carton1 floor1)
  )
)
)

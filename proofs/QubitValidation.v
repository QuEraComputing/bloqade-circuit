From Stdlib Require Import List String Bool.
From Stdlib Require Import Structures.OrderedTypeEx.
From Stdlib Require Import FSets.FSetList.
From Stdlib Require Import FSets.FSetFacts.
From Stdlib Require Import FSets.FSetProperties.

Import ListNotations.
Open Scope string_scope.

Module StringSet := FSetList.Make(String_as_OT).
Module SSF := FSetFacts.WFacts(StringSet).
Module SSP := FSetProperties.Properties(StringSet).


Definition elt := string.
Definition set := StringSet.t.

(*
   QubitValidation lattice for control-flow must/may analysis.

   Semantics for control flow:
     - Bottom: proven safe / never occurs (most precise)
     - Must s: definitely occurs on ALL execution paths with violations s
     - May s:  possibly occurs on SOME execution paths with violations s
     - Top:    unknown / no information (least precise)

   Lattice ordering (more precise --> less precise):
     Bottom ⊑ Must s ⊑ May s ⊑ Top
     Bottom ⊑ May s ⊑ Top

   Key properties:
     - Must s ⊔ Bottom = May s  (happens on some paths, not all)
     - Must s1 ⊔ Must s2 = Must (s1 ∪ s2)  (union of violations on all paths)
     - May s1 ⊔ May s2 = May (s1 ∪ s2)    (union of potential violations)

   This models control-flow analysis where we track:
     - Which violations definitely happen (Must)
     - Which violations might happen (May)
     - When we've proven safety (Bottom)
     - When we lack information (Top)
*)
Inductive QubitValidation : Type :=
  | Bottom : QubitValidation
  | Must : set -> QubitValidation
  | May  : set -> QubitValidation
  | Top  : QubitValidation.

Definition subsetb_prop (a b : set) : Prop := StringSet.Subset a b.

Definition join (x y : QubitValidation) : QubitValidation :=
  match x, y with
  | Bottom, Bottom => Bottom
  | Bottom, Must v => May v
  | Bottom, May v => May v
  | Bottom, Top => Top

  | Must vx, Bottom => May vx
  | Must vx, Must vy => Must (StringSet.union vx vy)
  | Must vx, May vy => May (StringSet.union vx vy)
  | Must _, Top => Top

  | May vx, Bottom => May vx
  | May vx, Must vy => May (StringSet.union vx vy)
  | May vx, May vy => May (StringSet.union vx vy)
  | May _, Top => Top

  | Top, _ => Top
  end.

Definition validation_eq (x y : QubitValidation) : bool :=
  match x, y with
  | Bottom, Bottom => true
  | Top, Top => true
  | Must a, Must b => StringSet.equal a b
  | May a, May b => StringSet.equal a b
  | _, _ => false
  end.

Definition subseteq (x y : QubitValidation) : Prop :=
  match x, y with
  | Bottom, _ => True
  | Must vx, Must vy => subsetb_prop vx vy
  | Must vx, May vy  => subsetb_prop vx vy
  | Must _, Top => True
  | May vx, May vy => subsetb_prop vx vy
  | May _, Top => True
  | Top, Top => True
  | _, _ => False
  end.

Definition QV_equiv (x y : QubitValidation) : Prop :=
  match x, y with
  | Bottom, Bottom => True
  | Top, Top => True
  | Must a, Must b => StringSet.Equal a b
  | May a, May b => StringSet.Equal a b
  | _, _ => False
  end.

Lemma set_equal_bool_iff : forall a b,
  StringSet.equal a b = true <-> StringSet.Equal a b.
  Proof.
    intros a b. split.
    - intros Heq. apply StringSet.equal_2. assumption.
    - intros H. apply StringSet.equal_1. assumption.
  Qed.

Theorem union_commutative_bool : forall a b,
  StringSet.equal (StringSet.union a b) (StringSet.union b a) = true.
  Proof.
    intros. apply StringSet.equal_1. apply SSP.union_sym.
  Qed.

Theorem inter_commutative_bool : forall a b,
  StringSet.equal (StringSet.inter a b) (StringSet.inter b a) = true.
  Proof.
    intros. apply StringSet.equal_1. apply SSP.inter_sym.
  Qed.

Theorem join_commutative : forall x y,
  QV_equiv (join x y) (join y x).
  Proof.
    intros x y. destruct x; destruct y;
    try simpl; try auto; try apply SSP.equal_refl.
    - unfold QV_equiv. simpl. apply SSP.union_sym.
    - unfold QV_equiv. simpl. apply SSP.union_sym.
    - unfold QV_equiv. simpl. apply SSP.union_sym.
    - unfold QV_equiv. simpl. apply SSP.union_sym.
  Qed.

Lemma join_upper_bound : forall x y,
  subseteq x (join x y) /\ subseteq y (join x y).
  Proof.
    intros x y. destruct x; destruct y.
    - split. unfold subseteq. auto. unfold subseteq. auto.
    - split. unfold subseteq. auto. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. assumption.
    - split. unfold subseteq. auto. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. assumption.
    - split. unfold subseteq. auto. unfold subseteq. simpl. auto.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. assumption. unfold subseteq. auto.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_2. assumption.
      unfold subseteq. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_3. assumption.
    - split. unfold subseteq. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_2. assumption.
      unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_3. assumption.
    - split. unfold subseteq. simpl. auto. unfold subseteq. simpl. auto.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. assumption. unfold subseteq. auto.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_2. assumption.
      unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_3. assumption.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_2. assumption.
      unfold subseteq. simpl. simpl. unfold subsetb_prop. intros x Hin. apply StringSet.union_3. assumption.
    - split. unfold subseteq. simpl. auto. unfold subseteq. simpl. auto.
    - split. unfold subseteq. simpl. simpl. unfold subsetb_prop. auto. unfold subseteq. auto.
    - split. unfold subseteq. simpl. auto. unfold subseteq. simpl. auto.
    - split. unfold subseteq. simpl. auto. unfold subseteq. simpl. auto.
    - split. unfold subseteq. simpl. auto. unfold subseteq. simpl. auto.
  Qed.

Theorem join_associative : forall x y z,
  QV_equiv (join (join x y) z) (join x (join y z)).
Proof.
  intros x y z.
  destruct x; destruct y; destruct z; simpl;
  unfold QV_equiv; simpl; try reflexivity;
  try apply SSP.equal_refl; try apply SSP.union_assoc.
Qed.

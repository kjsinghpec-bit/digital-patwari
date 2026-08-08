"""The explanation/query layer.

Every method here reads only from a ReconciledFardRecord (stage 4 of the
extraction pipeline -- see reconciliation.py). Nothing here touches raw
LLM output or re-derives anything the axiom gates and reconciliation
step haven't already checked. This is what makes answers explainable:
every Answer can point back to the exact validated field and evidence
it came from.

Every Answer that involves a judgment or a calculation carries:
  - record_says     : what is explicitly written in the source, verbatim
                       or near-verbatim.
  - calculated      : what deterministic arithmetic (exact Fraction math)
                       produces from validated fields. None if the inputs
                       needed for a calculation are missing or uncertain.
  - interpretation  : what Digital Patwari reasonably infers (e.g. an
                       ownership reconciliation note) -- never a guessed
                       fact, only a labeled inference about known facts.
  - evidence        : SourceReference(s) the answer is grounded in.
  - confidence      : the lowest ExtractionConfidence among the fields used.
  - uncertain        : True whenever any input status was illegible,
                       uncertain, not_present, missing, or ambiguous --
                       the abstention signal. When True, the caller
                       should show the user a "needs verification" state
                       rather than presenting the answer as settled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from digital_patwari.models import (
    ExtractionConfidence,
    ExtractionStatus,
    Khewat,
    Mutation,
    MutationStatus,
    Owner,
    Remark,
    RemarkTarget,
    SourceReference,
)
from digital_patwari.derived_ownership import (
    derive_khewat_ownership,
    format_fraction,
    format_over_denominator,
)
from digital_patwari.encumbrance import MortgageStatus, resolve_mortgage_status
from digital_patwari.interests import (
    classify_person_interest_scope,
    is_khud_kasht,
    resolve_cultivation_interests,
    resolve_parcel_interests,
)
from digital_patwari.normalization import raw_share_denominator
from digital_patwari.ownership import (
    EffectiveOwnershipInterest,
    OwnershipScope,
    resolve_owner_entitlements,
)
from digital_patwari.reconciliation import OwnershipStatus, ReconciledFardRecord


@dataclass(frozen=True)
class Answer:
    question: str
    record_says: str
    calculated: str | None
    interpretation: str | None
    evidence: list[SourceReference] = field(default_factory=list)
    confidence: ExtractionConfidence | None = None
    uncertain: bool = False
    uncertainty_reason: str | None = None
    # The three ownership states, populated only by answers that actually
    # reason about them (see derived_ownership.py). Kept as distinct fields
    # so a UI can never collapse "what the record says" into "what we
    # derived" -- they are different claims with different authority.
    mutation_effect: str | None = None
    derived_position: str | None = None
    possession_position: str | None = None


def _display_sarsahi(total_sarsahi: int, marla_per_kanal: int = 20, sarsahi_per_marla: int = 9) -> str:
    marla, sarsahi = divmod(total_sarsahi, sarsahi_per_marla)
    kanal, marla = divmod(marla, marla_per_kanal)
    return f"{kanal} kanal {marla} marla {sarsahi} sarsahi"


def khewat_total_area_sarsahi(
    khewat: Khewat, marla_per_kanal: int = 20, sarsahi_per_marla: int = 9
) -> tuple[int, bool, list[str]]:
    """Sum each Khatauni's own recorded_total_area exactly once. A Khewat
    with multiple Khataunis must never have its area multiplied by the
    number of Khataunis -- this is that guarantee, in one place."""
    total = 0
    missing: list[str] = []
    for khatauni in khewat.khataunis:
        if khatauni.recorded_total_area is None:
            missing.append(khatauni.khatauni_id)
            continue
        total += khatauni.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
    return total, not missing, missing


class FardQueryEngine:
    def __init__(self, record: ReconciledFardRecord, *, marla_per_kanal: int = 20, sarsahi_per_marla: int = 9) -> None:
        self.record = record
        self.marla_per_kanal = marla_per_kanal
        self.sarsahi_per_marla = sarsahi_per_marla

    # -- lookups -------------------------------------------------------

    def _all_owners(self) -> list[Owner]:
        return [owner for khewat in self.record.document.khewats for owner in khewat.owners]

    def _khewat_for(self, khewat_id: str) -> Khewat | None:
        for khewat in self.record.document.khewats:
            if khewat.khewat_id == khewat_id:
                return khewat
        return None

    def find_owners(self, name_query: str) -> list[Owner]:
        query = name_query.strip().lower()
        if not query:
            return []
        matches = []
        for owner in self._all_owners():
            haystacks = [owner.raw_owner_name_parentage.lower()]
            if owner.normalized_owner_name:
                haystacks.append(owner.normalized_owner_name.lower())
            if any(query in h for h in haystacks):
                matches.append(owner)
        return matches

    def _resolve_single_owner(self, name_query: str) -> tuple[Owner | None, str | None]:
        matches = self.find_owners(name_query)
        if not matches:
            return None, f"No owner matching '{name_query}' was found in this Fard."
        if len(matches) > 1:
            names = "; ".join(f"{o.raw_owner_name_parentage} (Khewat {o.khewat_id})" for o in matches)
            return None, f"'{name_query}' matches more than one owner: {names}. Please specify which one."
        return matches[0], None

    def _resolve_owner_rows(self, name_query: str) -> tuple[list[Owner] | None, Khewat | None, str | None]:
        """Group name matches by Khewat AND exact name -- a substring query
        can legitimately match two DIFFERENT people in the same Khewat
        (e.g. "Ram Singh" matching both "Ram Singh" and "Ram Singh Jr"),
        which must stay ambiguous. Only rows that share both the same
        Khewat and the exact same name string are treated as one real
        person's multiple ownership-interest rows (a Khewat-level default
        plus one or more Khatauni-level overrides) and resolved/summed
        together instead of raising a false ambiguity."""
        matches = self.find_owners(name_query)
        if not matches:
            return None, None, f"No owner matching '{name_query}' was found in this Fard."

        identity_keys = {(o.khewat_id, o.raw_owner_name_parentage.strip().lower()) for o in matches}
        if len(identity_keys) > 1:
            names = "; ".join(f"{o.raw_owner_name_parentage} (Khewat {o.khewat_id})" for o in matches)
            return None, None, f"'{name_query}' matches more than one owner: {names}. Please specify which one."

        khewat = self._khewat_for(matches[0].khewat_id)
        if khewat is None:
            return None, None, f"Owner references Khewat {matches[0].khewat_id}, which was not found in this document."
        return matches, khewat, None

    # -- who are the owners ---------------------------------------------

    def list_owners(self) -> Answer:
        owners = self._all_owners()
        if not owners:
            return Answer(
                question="Who are the recorded owners?",
                record_says="No owners were extracted from this document.",
                calculated=None, interpretation=None, uncertain=True,
                uncertainty_reason="No Owner records present.",
            )
        lines = [
            f"{o.raw_owner_name_parentage} -- Khewat {o.khewat_id}, share {o.raw_share_fraction}"
            + (" (uncertain/illegible)" if o.status != ExtractionStatus.PRESENT else "")
            for o in owners
        ]
        any_uncertain = any(o.status != ExtractionStatus.PRESENT for o in owners)
        return Answer(
            question="Who are the recorded owners?",
            record_says="\n".join(lines),
            calculated=f"{len(owners)} owner record(s) across {len(self.record.document.khewats)} Khewat(s).",
            interpretation=None,
            evidence=[o.source for o in owners if o.source],
            uncertain=any_uncertain,
            uncertainty_reason="One or more owner entries are marked illegible/uncertain/not_present." if any_uncertain else None,
        )

    # -- share ------------------------------------------------------------

    def owner_share(self, name_query: str) -> Answer:
        owners, khewat, error = self._resolve_owner_rows(name_query)
        if owners is None:
            return Answer(
                question=f"What is {name_query}'s share?",
                record_says=error or "Owner not found.",
                calculated=None, interpretation=None, uncertain=True, uncertainty_reason=error,
            )

        name = owners[0].raw_owner_name_parentage
        if len(owners) == 1:
            owner = owners[0]
            record_says = f"Raw share as recorded: {owner.raw_share_fraction}"
            calculated = f"Normalized exact share: {owner.share_fraction}"
        else:
            # One person can legitimately hold several ownership-interest
            # rows in one Khewat (a Khewat-level default plus one or more
            # Khatauni-level overrides) -- report each rather than
            # collapsing them into a single, meaningless combined fraction.
            lines = []
            for o in owners:
                scope = f"Khatauni {o.khatauni_id}" if o.khatauni_id is not None else f"Khewat {khewat.khewat_id} (default)"
                lines.append(f"{scope}: raw {o.raw_share_fraction}, normalized {o.share_fraction}")
            record_says = "Multiple ownership-interest rows for this owner:\n" + "\n".join(lines)
            calculated = None

        extraction_reason = (
            "Owner extraction status is 'uncertain'/'illegible'/'not_present' on one or more of this owner's rows."
            if any(o.status != ExtractionStatus.PRESENT for o in owners) else None
        )
        reconciliation_reason = self._reconciliation_flags_uncertain(owners)
        reasons = [r for r in (extraction_reason, reconciliation_reason) if r]
        sources = [o.source for o in owners if o.source]
        return Answer(
            question=f"What is {name}'s share?",
            record_says=record_says,
            calculated=calculated,
            interpretation=self._ownership_note(owners),
            evidence=sources,
            confidence=sources[0].confidence if sources else None,
            uncertain=bool(reasons),
            uncertainty_reason=" ".join(reasons) if reasons else None,
        )

    # -- land / area --------------------------------------------------------

    def owner_land(self, name_query: str) -> Answer:
        owners, khewat, error = self._resolve_owner_rows(name_query)
        if owners is None:
            return Answer(
                question=f"How much land does {name_query} have?",
                record_says=error or "Owner not found.",
                calculated=None, interpretation=None, uncertain=True, uncertainty_reason=error,
            )
        name = owners[0].raw_owner_name_parentage

        # Resolve every ownership-interest row this person holds in this
        # Khewat: each explicit Khatauni-level override contributes only
        # its own Khatauni's area; each Khewat-level (pooled) row
        # contributes only the area of Khataunis that actually inherit
        # from it (those with no explicit owner of their own). Every
        # Khatauni's area is drawn into exactly one interest -- never
        # zero (inheritance), never two (override exclusion) -- so summing
        # these interests can't double count and can't silently omit.
        interests = resolve_owner_entitlements(owners, khewat, self.marla_per_kanal, self.sarsahi_per_marla)

        interest_lines = []
        for interest in interests:
            scope_label = (
                f"Khatauni {interest.khatauni_ids[0]} (explicit)" if interest.scope == OwnershipScope.KHATAUNI
                else f"Khewat-level default, inherited by Khatauni(s) {', '.join(interest.khatauni_ids) or '(none -- all Khataunis have their own explicit owner)'}"
            )
            area_text = _display_sarsahi(interest.area_sarsahi) if interest.area_complete else "incomplete (missing recorded area)"
            interest_lines.append(f"{scope_label}: area {area_text}, share {interest.owner.share_fraction}")
        record_says = f"Ownership interests for {name} in Khewat {khewat.khewat_id}:\n" + "\n".join(interest_lines)

        any_incomplete = any(not i.area_complete for i in interests)
        any_owner_uncertain = any(o.status != ExtractionStatus.PRESENT for o in owners)
        if any_incomplete or any_owner_uncertain:
            missing_ids = sorted({kid for i in interests for kid in i.missing_khatauni_ids})
            return Answer(
                question=f"How much land does {name} have?",
                record_says=record_says,
                calculated=None,
                interpretation=self._ownership_note(owners),
                evidence=[s for s in [*(o.source for o in owners), khewat.source] if s],
                uncertain=True,
                uncertainty_reason=(
                    f"Khatauni(s) {', '.join(missing_ids)} have no recorded area." if any_incomplete
                    else "Owner extraction status is uncertain/illegible/not_present on one or more rows."
                ),
            )

        total_exact_sarsahi = sum((i.entitlement_sarsahi() for i in interests), Fraction(0))
        whole_sarsahi = int(total_exact_sarsahi)
        breakdown = " + ".join(
            f"{i.owner.share_fraction} of {_display_sarsahi(i.area_sarsahi)}" for i in interests
        )
        calculated = f"{breakdown} = {_display_sarsahi(whole_sarsahi)}"
        if total_exact_sarsahi != whole_sarsahi:
            calculated += f" (exact: {total_exact_sarsahi} sarsahi, truncated for display)"

        reconciliation_reason = self._reconciliation_flags_uncertain(owners)
        return Answer(
            question=f"How much land does {name} have?",
            record_says=record_says,
            calculated=calculated,
            interpretation=self._ownership_note(owners),
            evidence=[s for s in [*(o.source for o in owners), khewat.source] if s],
            confidence=owners[0].source.confidence if owners[0].source else None,
            uncertain=reconciliation_reason is not None,
            uncertainty_reason=reconciliation_reason,
        )

    # -- khasra context (never claimed as exclusive owner possession) ----

    def owner_khasra_context(self, name_query: str) -> Answer:
        owners, khewat, error = self._resolve_owner_rows(name_query)
        if owners is None:
            return Answer(
                question=f"Which Khasra numbers relate to {name_query}?",
                record_says=error or "Owner not found.",
                calculated=None, interpretation=None, uncertain=True, uncertainty_reason=error,
            )
        name = owners[0].raw_owner_name_parentage

        # Union the Khataunis actually resolved for this person's
        # interests (explicit overrides + Khataunis inherited via a
        # Khewat-level default) -- not every Khatauni in the Khewat.
        interests = resolve_owner_entitlements(owners, khewat, self.marla_per_kanal, self.sarsahi_per_marla)
        khatauni_ids_in_scope: list[str] = []
        for interest in interests:
            for kid in interest.khatauni_ids:
                if kid not in khatauni_ids_in_scope:
                    khatauni_ids_in_scope.append(kid)
        relevant_khataunis = [k for k in khewat.khataunis if k.khatauni_id in khatauni_ids_in_scope]

        khasra_numbers = [khs.khasra_number for kht in relevant_khataunis for khs in kht.khasras]
        scope_label = f"Khatauni(s) {', '.join(khatauni_ids_in_scope)}" if khatauni_ids_in_scope else f"Khewat {khewat.khewat_id}"
        if not khasra_numbers:
            return Answer(
                question=f"Which Khasra numbers relate to {name}?",
                record_says=f"No Khasra entries were extracted under {scope_label}.",
                calculated=None, interpretation=None, uncertain=True,
                uncertainty_reason=f"No Khasra records present under {scope_label}.",
            )
        return Answer(
            question=f"Which Khasra numbers relate to {name}?",
            record_says=f"Khasra numbers recorded under {scope_label}: {', '.join(khasra_numbers)}.",
            calculated=None,
            interpretation=(
                "Khasra numbers are a spatial description of the Khewat/Khatauni, not a direct "
                "owner-to-parcel assignment -- this Fard does not establish that this owner "
                "individually possesses any specific Khasra among these."
            ),
            evidence=[khewat.source] if khewat and khewat.source else [],
            uncertain=False,
        )

    # -- total land across every Khewat the owner appears in ---------------

    def owner_total_across_khewats(self, name_query: str) -> Answer:
        """A person can hold land in more than one Khewat. owner_land()
        deliberately abstains when a name spans multiple Khewats (protecting
        against merging two different people who share a name -- see
        owner_land's docstring). This method is the explicit "yes, trace
        this owner through the whole Fard" request: it still refuses to
        merge people whose exact name+parentage text differs, but for a
        single identity spanning several Khewats it resolves and sums each
        Khewat's entitlement independently, never merging the Khewats
        themselves and never treating one Khewat's area as another's."""
        matches = self.find_owners(name_query)
        if not matches:
            return Answer(
                question=f"What is {name_query}'s total land across this Fard?",
                record_says=f"No owner matching '{name_query}' was found in this Fard.",
                calculated=None, interpretation=None, uncertain=True,
                uncertainty_reason=f"No owner matching '{name_query}' was found in this Fard.",
            )

        identity_names = {m.raw_owner_name_parentage.strip().lower() for m in matches}
        if len(identity_names) > 1:
            names = "; ".join(f"{o.raw_owner_name_parentage} (Khewat {o.khewat_id})" for o in matches)
            return Answer(
                question=f"What is {name_query}'s total land across this Fard?",
                record_says=f"'{name_query}' matches more than one distinct owner: {names}. Please specify which one.",
                calculated=None, interpretation=None, uncertain=True,
                uncertainty_reason="Ambiguous: matches span more than one distinct name+parentage identity.",
            )

        name = matches[0].raw_owner_name_parentage
        khewat_ids = sorted({m.khewat_id for m in matches})

        per_khewat_lines: list[str] = []
        total_sarsahi = Fraction(0)
        any_incomplete = False
        any_uncertain_status = any(o.status != ExtractionStatus.PRESENT for o in matches)
        evidence: list[SourceReference] = []

        for khewat_id in khewat_ids:
            khewat = self._khewat_for(khewat_id)
            if khewat is None:
                any_incomplete = True
                per_khewat_lines.append(f"Khewat {khewat_id}: not found in this document (dangling reference).")
                continue
            rows = [m for m in matches if m.khewat_id == khewat_id]
            interests = resolve_owner_entitlements(rows, khewat, self.marla_per_kanal, self.sarsahi_per_marla)
            khewat_complete = all(i.area_complete for i in interests)
            khewat_sarsahi = sum((i.entitlement_sarsahi() for i in interests), Fraction(0))
            if not khewat_complete:
                any_incomplete = True
                per_khewat_lines.append(f"Khewat {khewat_id}: incomplete (missing recorded area for one or more Khataunis).")
            else:
                total_sarsahi += khewat_sarsahi
                per_khewat_lines.append(f"Khewat {khewat_id}: {_display_sarsahi(int(khewat_sarsahi))}")
            evidence.extend(s for s in (*(o.source for o in rows), khewat.source) if s)

        record_says = f"{name} appears in {len(khewat_ids)} Khewat(s):\n" + "\n".join(per_khewat_lines)
        interpretation = (
            "This total assumes every row sharing this exact name and parentage text refers to the same "
            "real person -- Fards carry no global person ID, so identical name+parentage is the strongest "
            "available signal, not a verified fact. Each Khewat is a legally distinct holding; this figure "
            "sums them, it does not merge them."
        )

        if any_incomplete or any_uncertain_status:
            return Answer(
                question=f"What is {name}'s total land across this Fard?",
                record_says=record_says, calculated=None, interpretation=interpretation,
                evidence=evidence, uncertain=True,
                uncertainty_reason=(
                    "One or more Khewats have incomplete area data." if any_incomplete
                    else "One or more of this owner's rows have an uncertain/illegible extraction status."
                ),
            )

        whole_sarsahi = int(total_sarsahi)
        calculated = f"Sum of {len(khewat_ids)} Khewat(s) = {_display_sarsahi(whole_sarsahi)}"
        if total_sarsahi != whole_sarsahi:
            calculated += f" (exact: {total_sarsahi} sarsahi, truncated for display)"

        reconciliation_reason = self._reconciliation_flags_uncertain(matches)
        return Answer(
            question=f"What is {name}'s total land across this Fard?",
            record_says=record_says, calculated=calculated, interpretation=interpretation,
            evidence=evidence, confidence=matches[0].source.confidence if matches[0].source else None,
            uncertain=reconciliation_reason is not None, uncertainty_reason=reconciliation_reason,
        )

    # -- current position: base vs mutation effect vs derived ---------------

    def owner_current_position(self, name_query: str) -> Answer:
        """"How much land does this person have NOW?"

        Never answers with the base Jamabandi share alone. Reports the three
        ownership states separately -- what the record says, what sanctioned
        mutations did to it, and the derived position -- plus the possession
        position, which is a different question again. Abstains when the
        derivation cannot be completed rather than presenting a figure."""
        owners, khewat, error = self._resolve_owner_rows(name_query)
        if owners is None:
            return Answer(
                question=f"How much land does {name_query} have now?",
                record_says=error or "Owner not found.",
                calculated=None, interpretation=None, uncertain=True, uncertainty_reason=error,
            )
        name = owners[0].raw_owner_name_parentage
        derived = derive_khewat_ownership(self.record.document, khewat)

        base_lines: list[str] = []
        effect_lines: list[str] = []
        derived_lines: list[str] = []
        failed = False
        failure_reasons: list[str] = []

        for owner in owners:
            position = derived.position_for_owner(owner.owner_id)
            if position is None:
                continue
            printed_denominator = raw_share_denominator(owner.raw_share_fraction)
            base_lines.append(f"Base Jamabandi share: {owner.raw_share_fraction} (as recorded)")

            if position.applied_effects:
                for effect in position.applied_effects:
                    # Render every fraction over the denominator the Fard
                    # printed, so the explanation can be checked against the
                    # page rather than against a reduced equivalent.
                    moved = format_over_denominator(abs(effect.share_delta), printed_denominator)
                    effect_lines.append(
                        f"{effect.description}: {moved} transferred. "
                        f"{format_over_denominator(effect.share_before, printed_denominator)} -> "
                        f"{format_over_denominator(effect.share_after, printed_denominator)}"
                    )
            if position.unapplied_mutation_ids:
                effect_lines.append(
                    f"Recorded but NOT applied ({', '.join(position.unapplied_mutation_ids)}): "
                    f"{position.unapplied_reason}"
                )
            if position.derivation_failed:
                failed = True
                if position.failure_reason:
                    failure_reasons.append(position.failure_reason)

            derived_lines.append(
                f"Derived share: {format_over_denominator(position.derived_share, printed_denominator)}"
                + ("" if position.changed else " (unchanged by any sanctioned mutation)")
            )

        possession = resolve_cultivation_interests(self.record.document, name)
        if possession:
            possession_text = "; ".join(
                f"Khatauni {c.khatauni_id}: {c.relationship.value}"
                + (f" (share {c.share_fraction})" if c.share_fraction else "")
                for c in possession
            )
        else:
            possession_text = (
                "No cultivation/possession (Girdawari) entry recorded for this person. This is not "
                "evidence that they do or do not possess the land -- it is simply not recorded here."
            )

        if failed:
            return Answer(
                question=f"How much land does {name} have now?",
                record_says="\n".join(base_lines),
                calculated=None,
                mutation_effect="\n".join(effect_lines) or None,
                derived_position=None,
                possession_position=possession_text,
                interpretation="The derived position could not be computed safely.",
                evidence=[s for s in (o.source for o in owners) if s],
                uncertain=True,
                uncertainty_reason=" ".join(failure_reasons),
            )

        return Answer(
            question=f"How much land does {name} have now?",
            record_says="\n".join(base_lines),
            calculated=None,
            mutation_effect="\n".join(effect_lines) if effect_lines else "No mutation affects this owner's share.",
            derived_position="\n".join(derived_lines),
            possession_position=possession_text,
            interpretation=(
                "The base Jamabandi entry is preserved exactly as recorded and is never rewritten. "
                "The derived position reflects only sanctioned mutations. Ownership and possession "
                "are separate questions and may legitimately differ."
            ),
            evidence=[s for s in (o.source for o in owners) if s],
            uncertain=False,
        )

    # -- specific-parcel (purchaser) interests -----------------------------

    def parcel_interests_for(self, person_name: str) -> Answer:
        """Specific-Khasra interests, area computed from the NAMED PARCELS
        only -- never a fraction of the enclosing Khewat."""
        resolved = resolve_parcel_interests(
            self.record.document, person_name, self.marla_per_kanal, self.sarsahi_per_marla
        )
        if not resolved:
            return Answer(
                question=f"Which specific Khasras does {person_name} hold?",
                record_says=f"No specific-parcel interest is recorded for '{person_name}' in this Fard.",
                calculated=None, interpretation=None, uncertain=False,
            )

        lines: list[str] = []
        total_sarsahi = 0
        any_incomplete = False
        any_non_operative = False
        for item in resolved:
            khasra_numbers = ", ".join(k.khasra_number for k in item.resolved_khasras) or "(none resolved)"
            lines.append(
                f"{item.interest.role.value} in Khewat {item.interest.khewat_id}: Khasra(s) {khasra_numbers}"
                + (f" [via mutation {item.interest.mutation_id}, status {item.mutation_status.value}]"
                   if item.mutation_status else "")
            )
            if item.unresolved_khasra_ids:
                any_incomplete = True
                lines.append(f"  Unresolved Khasra id(s): {', '.join(item.unresolved_khasra_ids)}")
            if not item.is_operative:
                any_non_operative = True
            if item.area_complete and item.is_operative:
                total_sarsahi += item.area_sarsahi

        calculated = (
            f"Sum of the named parcels' own areas = {_display_sarsahi(total_sarsahi)}"
            if not any_incomplete else None
        )
        return Answer(
            question=f"Which specific Khasras does {person_name} hold?",
            record_says="\n".join(lines),
            calculated=calculated,
            interpretation=(
                "This is a specific-parcel interest: the area is the sum of the named Khasras' own "
                "areas. It is NOT a fraction of the whole Khewat, and must never be calculated as one."
                + (" One or more of these interests arises from a mutation that is not sanctioned, so "
                   "it is claimed rather than confirmed." if any_non_operative else "")
            ),
            evidence=[i.interest.source for i in resolved if i.interest.source],
            uncertain=any_incomplete or any_non_operative,
            uncertainty_reason=(
                "Some named Khasras could not be resolved in the document." if any_incomplete
                else "Interest arises from a non-sanctioned mutation." if any_non_operative else None
            ),
        )

    def cultivation_position_for(self, person_name: str) -> Answer:
        """The Girdawari/possession position -- deliberately answered
        WITHOUT reference to ownership shares."""
        interests = resolve_cultivation_interests(self.record.document, person_name)
        if not interests:
            return Answer(
                question=f"What is {person_name}'s recorded cultivation/possession position?",
                record_says="No cultivation/possession (Girdawari) entry is recorded for this person.",
                calculated=None,
                interpretation=(
                    "Absence of a cultivation entry is not evidence about possession either way, and "
                    "says nothing about ownership."
                ),
                uncertain=False,
            )
        lines = [
            f"Khatauni {c.khatauni_id} (Khewat {c.khewat_id}): {c.relationship.value}"
            + (f", share {c.share_fraction}" if c.share_fraction else "")
            + (f' -- "{c.raw_relationship_text}"' if c.raw_relationship_text else "")
            for c in interests
        ]
        khud_kasht = [c for c in interests if is_khud_kasht(c)]
        return Answer(
            question=f"What is {person_name}'s recorded cultivation/possession position?",
            record_says="\n".join(lines),
            calculated=None,
            interpretation=(
                ("Khud Kasht is explicitly recorded, so this person is recorded as self-cultivating "
                 "the relevant holding. " if khud_kasht else "")
                + "Cultivation/possession is a separate dimension from ownership: a cultivator is not "
                "thereby an owner, and an owner need not be the recorded cultivator. A difference "
                "between the two is not automatically an error."
            ),
            evidence=[c.source for c in interests if c.source],
            uncertain=any(c.status != ExtractionStatus.PRESENT for c in interests),
        )

    def explain_term(self, text: str) -> Answer:
        """Explain Punjabi/Urdu/Persian revenue vocabulary found in a
        passage, carrying each term's validation level."""
        from digital_patwari.terminology import find_terms, is_reliable

        terms = find_terms(text)
        if not terms:
            return Answer(
                question=f'What does "{text}" mean?',
                record_says="No known revenue term was recognised in this text.",
                calculated=None,
                interpretation="Digital Patwari does not guess at unrecognised vocabulary.",
                uncertain=True,
                uncertainty_reason="Unrecognised term; human/expert reading required.",
            )
        lines = []
        for term in terms:
            line = f"{term.raw_term}: {term.meaning} [{term.category.value}, {term.validation.value}]"
            if term.caution:
                line += f"\n  Caution: {term.caution}"
            lines.append(line)
        unreliable = [t for t in terms if not is_reliable(t)]
        return Answer(
            question=f'What does "{text}" mean?',
            record_says="\n".join(lines),
            calculated=None,
            interpretation="A term's meaning establishes a role or classification only, never a legal conclusion.",
            uncertain=bool(unreliable),
            uncertainty_reason=(
                f"{len(unreliable)} term(s) need expert/manual validation before being relied upon."
                if unreliable else None
            ),
        )

    # -- mutations ----------------------------------------------------------

    def mutations_for(self, name_query: str) -> Answer:
        owners, khewat, error = self._resolve_owner_rows(name_query)
        if owners is None:
            return Answer(
                question=f"What mutations are recorded for {name_query}?",
                record_says=error or "Owner not found.",
                calculated=None, interpretation=None, uncertain=True, uncertainty_reason=error,
            )
        name = owners[0].raw_owner_name_parentage
        owner_ids = {o.owner_id for o in owners}
        owner_mutations = [
            m for m in self.record.document.mutations
            if m.target_type == RemarkTarget.OWNER and m.target_id in owner_ids
        ]
        khewat_mutations = [
            m for m in self.record.document.mutations
            if m.target_type == RemarkTarget.KHEWAT and m.target_id == khewat.khewat_id
        ]
        all_mutations = owner_mutations + khewat_mutations
        if not all_mutations:
            return Answer(
                question=f"What mutations are recorded for {name}?",
                record_says="No mutation (Inteqal) entries are recorded against this owner or their Khewat.",
                calculated=None, interpretation=None, uncertain=False,
            )
        lines = [self._describe_mutation(m) for m in all_mutations]
        return Answer(
            question=f"What mutations are recorded for {name}?",
            record_says="\n".join(lines),
            calculated=None,
            interpretation=self._mutation_list_note(all_mutations),
            evidence=[m.source for m in all_mutations if m.source],
            uncertain=any(m.extraction_status != ExtractionStatus.PRESENT for m in all_mutations),
        )

    # -- mortgage / rehin status ------------------------------------------

    def mortgage_status_for(self, target_type: RemarkTarget, target_id: str) -> Answer:
        finding = resolve_mortgage_status(self.record.document, target_type, target_id)
        if finding.status == MortgageStatus.NO_MORTGAGE_DETECTED:
            return Answer(
                question=f"Is there a mortgage on {target_type.value} {target_id}?",
                record_says=finding.note, calculated=None, interpretation=None, uncertain=False,
            )
        mortgage_lines = [self._describe_mutation(m) for m in finding.mortgage_mutations]
        discharge_lines = [self._describe_mutation(m) for m in finding.discharge_mutations]
        record_says = "Mortgage entries:\n" + "\n".join(mortgage_lines)
        if discharge_lines:
            record_says += "\n\nDischarge/release entries:\n" + "\n".join(discharge_lines)
        return Answer(
            question=f"Is there a mortgage on {target_type.value} {target_id}?",
            record_says=record_says,
            calculated=None,
            interpretation=f"[{finding.status.value}] {finding.note}",
            evidence=[m.source for m in (*finding.mortgage_mutations, *finding.discharge_mutations) if m.source],
            uncertain=finding.status in (MortgageStatus.ACTIVE_MORTGAGE_LIKELY, MortgageStatus.UNCLEAR),
            uncertainty_reason=finding.note if finding.status in (MortgageStatus.ACTIVE_MORTGAGE_LIKELY, MortgageStatus.UNCLEAR) else None,
        )

    @staticmethod
    def _describe_mutation(m: Mutation) -> str:
        parts = [f"[{m.status.value}]"]
        if m.mutation_type:
            parts.append(m.mutation_type.value)
        if m.transfer_scope:
            parts.append(f"scope={m.transfer_scope.value}")
        if m.affected_khasra_numbers:
            parts.append(f"khasra(s)={','.join(m.affected_khasra_numbers)}")
        parts.append(f'-- "{m.raw_text}"')
        if m.parsed_meaning:
            parts.append(f"(meaning: {m.parsed_meaning})")
        return " ".join(parts)

    # -- remarks / Column 8 --------------------------------------------------

    def remarks_for(self, target_type: RemarkTarget, target_id: str) -> Answer:
        matches = [
            r for r in self.record.document.remarks
            if r.target_type == target_type and r.target_id == target_id
        ]
        if not matches:
            return Answer(
                question=f"What does Column 8 say for {target_type.value} {target_id}?",
                record_says="No Column 8 remarks are recorded for this entity.",
                calculated=None, interpretation=None, uncertain=False,
            )
        lines = [
            f"[{r.remark_category.value}] \"{r.raw_text}\""
            + (f" (meaning: {r.parsed_meaning})" if r.parsed_meaning else "")
            for r in matches
        ]
        return Answer(
            question=f"What does Column 8 say for {target_type.value} {target_id}?",
            record_says="\n".join(lines),
            calculated=None, interpretation=None,
            evidence=[r.source for r in matches if r.source],
            uncertain=False,
        )

    # -- total area -----------------------------------------------------------

    def total_area(self, khewat_id: str | None = None) -> Answer:
        if khewat_id is not None:
            khewat = self._khewat_for(khewat_id)
            if khewat is None:
                return Answer(
                    question=f"What is the total area of Khewat {khewat_id}?",
                    record_says=f"Khewat {khewat_id} was not found in this document.",
                    calculated=None, interpretation=None, uncertain=True,
                    uncertainty_reason="Unknown Khewat ID.",
                )
            total_sarsahi, complete, missing = khewat_total_area_sarsahi(khewat, self.marla_per_kanal, self.sarsahi_per_marla)
            note = None if complete else f"Incomplete: Khatauni(s) {', '.join(missing)} missing recorded area."
            return Answer(
                question=f"What is the total area of Khewat {khewat_id}?",
                record_says=f"Sum of each Khatauni's own recorded_total_area under Khewat {khewat_id} (each counted once).",
                calculated=_display_sarsahi(total_sarsahi),
                interpretation=note,
                uncertain=not complete,
                uncertainty_reason=note,
            )

        grand_total = 0
        any_missing = False
        for khewat in self.record.document.khewats:
            total_sarsahi, complete, _missing = khewat_total_area_sarsahi(khewat, self.marla_per_kanal, self.sarsahi_per_marla)
            grand_total += total_sarsahi
            any_missing = any_missing or not complete
        return Answer(
            question="What is the total area of this Fard?",
            record_says=f"Sum across {len(self.record.document.khewats)} Khewat(s), each Khatauni counted exactly once.",
            calculated=_display_sarsahi(grand_total),
            interpretation="Partial: some Khataunis are missing a recorded area and are excluded from this total." if any_missing else None,
            uncertain=any_missing,
            uncertainty_reason="One or more Khataunis have no recorded area." if any_missing else None,
        )

    # -- simple-English summary ------------------------------------------------

    def explain_fard_simple_english(self) -> Answer:
        header = self.record.document.document_header
        n_khewats = len(self.record.document.khewats)
        n_owners = len(self._all_owners())
        total_answer = self.total_area()
        n_approved = sum(1 for m in self.record.document.mutations if m.status == MutationStatus.APPROVED)
        n_pending = sum(1 for m in self.record.document.mutations if m.status == MutationStatus.PENDING)

        lines = [
            f"Village: {header.village} (Hadbast {header.hadbast_number}), Jamabandi year {header.jamabandi_year}.",
            f"This Fard records {n_khewats} Khewat(s) with {n_owners} owner entr(y/ies).",
            f"Total recorded area: {total_answer.calculated}"
            + (" (partial -- see uncertainty note)" if total_answer.uncertain else "") + ".",
            f"Mutations: {n_approved} approved, {n_pending} pending.",
            f"Axiom gate validation: {'PASSED' if self.record.validation_report.passed else 'FAILED -- see validation report for specifics'}.",
        ]
        return Answer(
            question="Explain this Fard in simple English.",
            record_says="\n".join(lines),
            calculated=None, interpretation=None,
            uncertain=not self.record.validation_report.passed or total_answer.uncertain,
            uncertainty_reason=None if self.record.validation_report.passed else "One or more axiom gates failed; treat this document as unverified.",
        )

    # -- internal --------------------------------------------------------------

    @staticmethod
    def _mutation_list_note(mutations: list[Mutation]) -> str | None:
        if any(m.status == MutationStatus.APPROVED for m in mutations):
            return (
                "CAUTION: one or more of these mutations is approved/sanctioned. Per the Approved "
                "Mutation Rule, active ownership may differ from the plain Fard row -- verify against "
                "the mutation record rather than assuming the row alone."
            )
        if any(m.status == MutationStatus.PENDING for m in mutations):
            return (
                "All recorded mutations here are pending/unsanctioned. Per the Pending Mutation Rule, "
                "active ownership as recorded in the Fard is unchanged; this is noted only as an "
                "encumbrance."
            )
        return None

    def _reconciliation_flags_uncertain(self, owners: list[Owner]) -> str | None:
        """An Answer that asserts a *current* share or land figure must be
        flagged for verification whenever an approved mutation may have
        superseded the ownership as recorded for ANY of this person's
        ownership-interest rows -- the calculation itself is correct "as
        recorded", but "as recorded" may no longer be current."""
        for owner in owners:
            reconciliation = self.record.reconciliation_for_owner(owner.owner_id)
            if reconciliation and reconciliation.status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION:
                return (
                    "An approved mutation affecting this owner or their Khewat is recorded; "
                    "the figure above reflects the Fard as recorded and may no longer be current."
                )
        return None

    def _ownership_note(self, owners: list[Owner]) -> str:
        notes = []
        for owner in owners:
            reconciliation = self.record.reconciliation_for_owner(owner.owner_id)
            if reconciliation is None:
                notes.append("No ownership reconciliation entry found for one of this owner's rows.")
            elif reconciliation.status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION:
                notes.append(f"CAUTION: {reconciliation.note}")
            else:
                notes.append(reconciliation.note)
        # De-duplicate while preserving order (multiple rows in the same
        # Khewat often share the same Khewat-level reconciliation note).
        seen: list[str] = []
        for n in notes:
            if n not in seen:
                seen.append(n)
        return " / ".join(seen) if seen else "No ownership reconciliation entry found for this owner."

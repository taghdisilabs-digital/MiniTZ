// Copyright Biella Games. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "BiellaGamesGameState.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include <limits>

namespace
{
class FBiellaArenaPressureScenario final : public IAutomationLatentCommand
{
public:
    explicit FBiellaArenaPressureScenario(FAutomationTestBase* InTest)
        : Test(InTest), WallStart(FPlatformTime::Seconds())
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() - WallStart > 30.0)
        {
            return Fail(TEXT("Arena-pressure state scenario exceeded its wall-clock bound"));
        }
        if (!World.IsValid())
        {
            if (GEngine)
            {
                for (const FWorldContext& Context : GEngine->GetWorldContexts())
                {
                    UWorld* Candidate = Context.World();
                    if (Candidate && Candidate->IsGameWorld() && Candidate->HasBegunPlay())
                    {
                        World = Candidate;
                        break;
                    }
                }
            }
            if (!World.IsValid())
            {
                return false;
            }
        }

        State = World->GetGameState<ABiellaGamesGameState>();
        if (!State.IsValid())
        {
            return Fail(TEXT("Canonical runtime did not create ABiellaGamesGameState"));
        }
        if (!Test->TestTrue(TEXT("Arena pressure is server-authoritative"), State->HasAuthority()) ||
            !Test->TestEqual(TEXT("Arena pressure has the canonical runtime identity"),
                State->ArenaPressureId, FName(TEXT("Demo01ArenaPressure"))) ||
            !Test->TestEqual(TEXT("Arena pressure starts inactive"),
                static_cast<uint8>(State->ArenaPressureState),
                static_cast<uint8>(EDemo01ArenaPressureState::Inactive)) ||
            !Test->TestEqual(TEXT("Arena pressure starts at zero"), State->ArenaPressure, 0.0f) ||
            !Test->TestEqual(TEXT("Arena pressure starts at revision zero"),
                State->GetArenaPressureRevision(), 0))
        {
            return Fail(TEXT("Arena-pressure initial authoritative state is invalid"));
        }

        if (!Test->TestTrue(TEXT("Negative pressure clamps to the inactive domain"),
                State->SetArenaPressure(-10.0f, TEXT("D01-032 negative-domain"))) ||
            !Test->TestEqual(TEXT("Clamped inactive pressure does not create a revision"),
                State->GetArenaPressureRevision(), 0) ||
            !Test->TestFalse(TEXT("Non-finite pressure is rejected"),
                State->SetArenaPressure(std::numeric_limits<float>::quiet_NaN(), TEXT("D01-032 invalid"))))
        {
            return Fail(TEXT("Arena-pressure input validation failed"));
        }

        if (!SetAndCheck(20.0f, EDemo01ArenaPressureState::Rising, 1, TEXT("rising")) ||
            !SetAndCheck(50.0f, EDemo01ArenaPressureState::Elevated, 2, TEXT("elevated")) ||
            !SetAndCheck(85.0f, EDemo01ArenaPressureState::Critical, 3, TEXT("critical")))
        {
            return Fail(TEXT("Arena-pressure deterministic state transitions failed"));
        }

        const int32 RevisionBeforeNoOp = State->GetArenaPressureRevision();
        if (!Test->TestTrue(TEXT("Repeated pressure value is accepted as a no-op"),
                State->SetArenaPressure(85.0f, TEXT("D01-032 no-op"))) ||
            !Test->TestEqual(TEXT("No-op pressure does not advance the revision"),
                State->GetArenaPressureRevision(), RevisionBeforeNoOp) ||
            !SetAndCheck(0.0f, EDemo01ArenaPressureState::Inactive, 4, TEXT("reset")))
        {
            return Fail(TEXT("Arena-pressure revision or reset semantics failed"));
        }

        UE_LOG(LogTemp, Display,
            TEXT("D01_032_TEST COMPLETE id=%s transitions=4 revisions=1,2,3,4 authority=server"),
            *State->ArenaPressureId.ToString());
        return true;
    }

private:
    bool SetAndCheck(float Level, EDemo01ArenaPressureState ExpectedState,
        int32 ExpectedRevision, const TCHAR* Phase)
    {
        if (!Test->TestTrue(FString::Printf(TEXT("Pressure transition %s is accepted"), Phase),
                State->SetArenaPressure(Level, FString::Printf(TEXT("D01-032 %s"), Phase))) ||
            !Test->TestEqual(FString::Printf(TEXT("Pressure level %s is authoritative"), Phase),
                State->ArenaPressure, Level) ||
            !Test->TestEqual(FString::Printf(TEXT("Pressure state %s is deterministic"), Phase),
                static_cast<uint8>(State->ArenaPressureState), static_cast<uint8>(ExpectedState)) ||
            !Test->TestEqual(FString::Printf(TEXT("Pressure revision %s is monotonic"), Phase),
                State->GetArenaPressureRevision(), ExpectedRevision) ||
            !Test->TestEqual(FString::Printf(TEXT("Pressure reason %s is retained"), Phase),
                State->ArenaPressureReason, FString::Printf(TEXT("D01-032 %s"), Phase)))
        {
            return false;
        }
        UE_LOG(LogTemp, Display,
            TEXT("D01_032_TEST STATE phase=%s id=%s state=%s level=%.1f revision=%d authority=server"),
            Phase, *State->ArenaPressureId.ToString(),
            *StaticEnum<EDemo01ArenaPressureState>()->GetNameStringByValue(
                static_cast<int64>(State->ArenaPressureState)),
            State->ArenaPressure, State->GetArenaPressureRevision());
        return true;
    }

    bool Fail(const TCHAR* Message)
    {
        Test->AddError(Message);
        return true;
    }

    FAutomationTestBase* Test;
    double WallStart;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ABiellaGamesGameState> State;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBiellaArenaPressureTest,
    "BiellaGames.Demo01.ArenaPressure",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FBiellaArenaPressureTest::RunTest(const FString& Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FBiellaArenaPressureScenario(this));
    return true;
}

#endif

// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class BiellaGamesTarget : TargetRules
{
	public BiellaGamesTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		
		ExtraModuleNames.Add("BiellaGames");
	}
}

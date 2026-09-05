// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class BiellaGamesEditorTarget : TargetRules
{
	public BiellaGamesEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		
		ExtraModuleNames.Add("BiellaGames");
	}
}

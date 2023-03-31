
import { useEffect, useState } from "react"
import { StateControlCheckbox, useStateControlCheckbox } from "../hooks/useStateControlCheckbox";
import { OpenAdvancedSettingCheckbox, OpenConverterSettingCheckbox, OpenDeviceSettingCheckbox, OpenModelSettingCheckbox, OpenQualityControlCheckbox, OpenServerControlCheckbox, OpenSpeakerSettingCheckbox } from "../const"
export type StateControls = {
    openServerControlCheckbox: StateControlCheckbox
    openModelSettingCheckbox: StateControlCheckbox
    openDeviceSettingCheckbox: StateControlCheckbox
    openQualityControlCheckbox: StateControlCheckbox
    openSpeakerSettingCheckbox: StateControlCheckbox
    openConverterSettingCheckbox: StateControlCheckbox
    openAdvancedSettingCheckbox: StateControlCheckbox

    showLicenseCheckbox: StateControlCheckbox
}

type FrontendManagerState = {
    stateControls: StateControls
    isConverting: boolean,
    isAnalyzing: boolean
};

export type FrontendManagerStateAndMethod = FrontendManagerState & {
    setIsConverting: (val: boolean) => void
    setIsAnalyzing: (val: boolean) => void
}

export const useFrontendManager = (): FrontendManagerStateAndMethod => {
    const [isConverting, setIsConverting] = useState<boolean>(false)
    const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)

    // (1) Controller Switch
    const openServerControlCheckbox = useStateControlCheckbox(OpenServerControlCheckbox);
    const openModelSettingCheckbox = useStateControlCheckbox(OpenModelSettingCheckbox);
    const openDeviceSettingCheckbox = useStateControlCheckbox(OpenDeviceSettingCheckbox);
    const openQualityControlCheckbox = useStateControlCheckbox(OpenQualityControlCheckbox);
    const openSpeakerSettingCheckbox = useStateControlCheckbox(OpenSpeakerSettingCheckbox);
    const openConverterSettingCheckbox = useStateControlCheckbox(OpenConverterSettingCheckbox);
    const openAdvancedSettingCheckbox = useStateControlCheckbox(OpenAdvancedSettingCheckbox);


    const showLicenseCheckbox = useStateControlCheckbox("leave-checkbox");

    useEffect(() => {
        openServerControlCheckbox.updateState(true)

    }, [])


    const returnValue = {
        stateControls: {
            openServerControlCheckbox,
            openModelSettingCheckbox,
            openDeviceSettingCheckbox,
            openQualityControlCheckbox,
            openSpeakerSettingCheckbox,
            openConverterSettingCheckbox,
            openAdvancedSettingCheckbox,

            showLicenseCheckbox
        },
        isConverting,
        setIsConverting,
        isAnalyzing,
        setIsAnalyzing
    };
    return returnValue;
};

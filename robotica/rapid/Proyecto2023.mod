    MODULE Module1
    CONST robtarget Target_90_esquina1:=[[-44.88,767.29,719.81],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_100_esquina2:=[[-44.88,717.29,719.81],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_110_esquina3:=[[5.12,717.29,719.81],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_120_esquina4:=[[5.12,767.29,719.81],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_20_CargarAprox:=[[25,0,-200],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];    
    CONST robtarget Target_10_CargrarStart:=[[0,0,-5],[1,0,0,0],[0,-1,1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];           
    CONST robtarget Target_40_DescargaInicio:=[[0,0,-200],[1,0,0,0],[1,-1,1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];    
    CONST robtarget Target_50_Rotar:=[[-19.88,742.29,920],[0,0,1,0],[0,0,1,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_80_aprox_pintarGrande:=[[-44.88,767.29,740],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_90_aprox_pintarPeq:=[[-19.88,722.29,640],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_90_Vertice1:=[[-19.88,722.29,620],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_100_Vertice2:=[[-39.88,762.29,620],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget Target_110_Vertice3:=[[0.12,762.29,620],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    PROC main()
        VAR num contador:=0; !poner:  =0 si queremos que empiece por la pequeña ; =1 si queremos que empiece por la grande
        WHILE contador<200 DO 
            contador:=contador+1;
            SetDO Salida,0;
            SetDO PosicionadorOutput, 0;
            SetDO MoverCajaPeq, 0;
            SetDO PosicionadorPeq, 0;
            SetDO MoverCajaGrande, 0;
            IF contador MOD 2=0 THEN !Si el contador es par; en c++ seria: if(contador%2==0)
                Path_0_startGrande;    
                 
            ELSE !Si el contador es impar
                Path_0_StartPeq;
            ENDIF
            
            IF CajaGrande=1 THEN     
                Path_10_CajaGrande;
            ELSE
                Path_20_CajaPeq;
            ENDIF
            
        ENDWHILE
    ENDPROC
    
        
    
    PROC Path_0_startGrande()
        SetDO ShowGrande, 1;
        SetDO HideGrande, 0;
        SetDO ShowPeq, 0;
        SetDO HidePeq, 1;
        MoveJdo Target_20_CargarAprox,v600,z50,VacuumTool\WObj:=Workobject_Cargar, MoverCajaGrande, 1;
        WaitDI Entrada,1;
        SetDO MoverCajaGrande, 0;
    ENDPROC 
    
    PROC Path_0_StartPeq()
        SetDO HideGrande, 1;
        SetDO ShowGrande, 0;
        SetDO HidePeq, 0;
        SetDO ShowPeq, 1;
        MoveJdo Target_20_CargarAprox,v600,z50,VacuumTool\WObj:=Workobject_Cargar, MoverCajaPeq, 1;
        WaitDI Entrada,1;
        SetDO MoverCajaPeq, 0;
    ENDPROC 
    
    PROC Path_10_CajaGrande()
        MoveJ offs(Target_10_CargrarStart, 0, 0, -50),v200,z30,VacuumTool\WObj:=Workobject_Cargar;
        MoveLDO Target_10_CargrarStart,v30,fine,VacuumTool\WObj:=Workobject_Cargar,Salida,1;!vacuum agarra la caja
        WaitTime 2;        
        MoveL Offs(Target_20_CargarAprox, -25, 0, 0),v30,fine,VacuumTool\WObj:=Workobject_Cargar;
        MoveJ Target_40_DescargaInicio,v200,z30,VacuumTool\WObj:=Workobject_Descarga;!mas despacio pq esta cargando la caja 
        MoveL Offs(Target_40_DescargaInicio, 0, 0, 195), v30, fine,VacuumTool\WObj:=Workobject_Descarga;
        SetDO Salida,0;        
        WaitTime 2;
        MoveL Offs(Target_40_DescargaInicio, 0, 0, 145),v30,fine,VacuumTool\WObj:=Workobject_Descarga;        
        MoveJ Target_40_DescargaInicio, v200,z30,VacuumTool\WObj:=Workobject_Descarga; 
        MoveJ Target_40_DescargaInicio,v100,z30,PenTool\WObj:=Workobject_Descarga;  
        MoveJ Target_80_aprox_pintarGrande,v200,z20,PenTool\WObj:=Workobject_pen;
        MoveL Target_90_esquina1,v10,fine,PenTool\WObj:=Workobject_pen; !vel muy baja pq un boli esta tocando la caja
        MoveL Target_100_esquina2,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_110_esquina3,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_120_esquina4,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_90_esquina1,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_80_aprox_pintarGrande,v30,fine,PenTool\WObj:=Workobject_pen;
        MoveJdo Target_40_DescargaInicio,v200,z30,PenTool\WObj:=Workobject_Descarga, PosicionadorOutput, 1;     
    ENDPROC
    
    PROC Path_20_CajaPeq()        
        MoveJ offs(Target_10_CargrarStart, 50, 0, 50),v200,z30,VacuumTool\WObj:=Workobject_Cargar;
        MoveLDO Offs(Target_10_CargrarStart, 50, 0, 100),v30,fine,VacuumTool\WObj:=Workobject_Cargar, Salida, 1;
        WaitTime 2;
        MoveL Offs(Target_20_CargarAprox, 25, 0, 100),v30,fine,VacuumTool\WObj:=Workobject_Cargar;!!como la caja es 100mm mas pequeña, la levanto 100mm para aumentar la velocidad del proceso sin disminuir la seguridad     
        MoveJ Offs (Target_40_DescargaInicio, 0, 0, 100),v200,z30,VacuumTool\WObj:=Workobject_Descarga; !mas despacio pq esta cargando la caja ;como la caja es 100mm mas pequeña, la levanto 100mm para aumentar la velocidad del proceso sin disminuir la seguridad     
        MoveL Offs(Target_40_DescargaInicio, 0, 0, 295.29),v30,fine,VacuumTool\WObj:=Workobject_Descarga;
        SetDO Salida,0;        
        WaitTime 2;
        MoveL Offs(Target_40_DescargaInicio, 0, 0, 245.29),v30,fine,VacuumTool\WObj:=Workobject_Descarga; 
        MoveJ Offs(Target_40_DescargaInicio, 0,0 ,100),v200,z30,VacuumTool\WObj:=Workobject_Descarga; 
        MoveJ Offs(Target_40_DescargaInicio, 0,0 ,100),v100,z30,PenTool\WObj:=Workobject_Descarga; !primero lo llevo a descargaInicio y luego lo roto por seguridad para que la herramienta no golpee la caja
        MoveJ Target_90_aprox_pintarPeq,v200,z20,PenTool\WObj:=Workobject_pen;
        MoveL Target_90_Vertice1,v10,fine,PenTool\WObj:=Workobject_pen; !vel muy baja pq un boli esta tocando la caja
        MoveL Target_100_Vertice2,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_110_Vertice3,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_90_Vertice1,v10,fine,PenTool\WObj:=Workobject_pen;
        MoveL Target_90_aprox_pintarPeq,v10,fine,PenTool\WObj:=Workobject_pen;     
        MoveJdo Offs(Target_40_DescargaInicio, 0,0 ,100),v200,z30,PenTool\WObj:=Workobject_Descarga, PosicionadorPeq, 1;        
    ENDPROC   
    PROC Path_0()

    ENDPROC
! En moveJ uso 3 vels: v600 para volver al estado inicial, v200 para cargar la caja o aproximarse a los puntos de aproximacion, v100 para rotar la herramienta
! En moveL uso 2 vels: v30 para aproximarse desde los ptos de aproximacion, v10 para pintar
ENDMODULE